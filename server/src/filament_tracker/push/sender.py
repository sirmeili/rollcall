"""The background phone sender: phone notifications are handed over after the work commits,
so a move or a save never waits for a push service or fails because of it. Each message is
built by its phone's route (messages.py), which also says what each answer means.

- A gone endpoint (404 or 410) is dropped at once.
- A failure worth trying again (a timeout, a 5xx, a 429, or FCM refusing its access token) is
  retried 3 times over about 15 minutes, then given up and counted on the endpoint.
- Any other failure (another 4xx) is given up at once and counted.

An endpoint with no success in 30 days is dropped by the stale-endpoint sweep (stale.py).

There is no stored outbox, so pushes still waiting are lost on a restart. Logs name the
device only: never the endpoint URL, its keys or the payload.
"""

import heapq
import itertools
import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.db.types import utcnow
from filament_tracker.push.firebase import Firebase
from filament_tracker.push.keys import VapidKeys
from filament_tracker.push.messages import Messages, Outcome, Push, Result
from filament_tracker.push.transport import PushError, PushTransport

logger = logging.getLogger(__name__)

# The waits before each retry: 1, 4 and 10 minutes, so 15 minutes in all.
RETRIES = (60.0, 240.0, 600.0)
STOP_TIMEOUT = 5.0
UNEXPECTED = "The phone notification couldn't be sent."


@dataclass(order=True)
class _Pending:
    due: float
    order: int
    push: Push
    attempt: int = 0


class PushSender:
    def __init__(
        self,
        transport: PushTransport,
        sessions: sessionmaker[Session],
        keys: VapidKeys,
        *,
        firebase: Callable[[], Firebase | None] = lambda: None,
        retries: tuple[float, ...] = RETRIES,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._transport = transport
        self._messages = Messages(transport, sessions, keys, firebase)
        self._sessions = sessions
        self._retries = retries
        self._clock = clock
        self._pending: list[_Pending] = []
        self._order = itertools.count()
        self._wake = threading.Condition()
        self._busy = False
        self._stopping = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="push-sender", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._wake:
            self._stopping = True
            self._wake.notify_all()
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT)

    def send_later(self, pushes: Iterable[Push]) -> None:
        """Queue pushes to send in the background. Returns at once."""
        with self._wake:
            for push in pushes:
                heapq.heappush(self._pending, _Pending(time.monotonic(), next(self._order), push))
            self._wake.notify_all()

    def idle(self) -> bool:
        """Nothing queued and nothing being sent."""
        with self._wake:
            return not self._pending and not self._busy

    def send_now(self, push: Push) -> Result:
        """Send one push and wait for the result, with no retries. A gone endpoint is still
        dropped; a failure isn't counted, as no notification was given up."""
        return self._send(push)

    def _run(self) -> None:
        while True:
            with self._wake:
                item = self._next()
                if item is None:
                    return
                self._busy = True
            try:
                self._attempt(item)
            finally:
                with self._wake:
                    self._busy = False

    def _next(self) -> _Pending | None:
        """The next push that is due, waiting for one; None once stopping."""
        while not self._stopping:
            if self._pending:
                wait = self._pending[0].due - time.monotonic()
                if wait <= 0:
                    return heapq.heappop(self._pending)
                self._wake.wait(wait)
            else:
                self._wake.wait()
        return None

    def _attempt(self, item: _Pending) -> None:
        result = self._send(item.push)
        if result.outcome not in (Outcome.FAILED, Outcome.REFUSED):
            return
        if result.outcome == Outcome.FAILED and item.attempt < len(self._retries):
            with self._wake:
                item.due = time.monotonic() + self._retries[item.attempt]
                item.attempt += 1
                heapq.heappush(self._pending, item)
                self._wake.notify_all()
            return
        self._give_up(item.push.device_id, result.message, item.attempt + 1)

    def _send(self, push: Push) -> Result:
        try:
            built = self._messages.build(push)
            if isinstance(built, Result):
                return built
            status = self._transport.post(built.message)
        except PushError as error:
            return Result(Outcome.FAILED, str(error))
        except Exception as error:
            # Only the type: an unexpected error's text could hold anything.
            logger.warning("phone notification: unexpected %s while sending", type(error).__name__)
            return Result(Outcome.FAILED, UNEXPECTED)
        result = self._messages.answered(built.route, status)
        if result.outcome == Outcome.SENT:
            self._update(push.device_id, self._succeeded)
        elif result.outcome == Outcome.GONE:
            self._update(push.device_id, self._drop)
            logger.info("phone %s's push endpoint is gone, so it was dropped", push.device_id)
        return result

    def _update(self, device_id: str, change: Callable[[Session, PushEndpoint], None]) -> None:
        with self._sessions() as session:
            endpoint = session.get(PushEndpoint, device_id)
            if endpoint is not None:
                change(session, endpoint)
                session.commit()

    def _succeeded(self, session: Session, endpoint: PushEndpoint) -> None:
        endpoint.last_success_at = self._clock()
        endpoint.failures = 0
        endpoint.failing_since = None

    def _drop(self, session: Session, endpoint: PushEndpoint) -> None:
        session.delete(endpoint)

    def _give_up(self, device_id: str, reason: str, tries: int) -> None:
        logger.warning(
            "a phone notification to phone %s was given up after %d tries: %s",
            device_id,
            tries,
            reason,
        )

        def count(session: Session, endpoint: PushEndpoint) -> None:
            endpoint.failures += 1
            if endpoint.failing_since is None:
                endpoint.failing_since = self._clock()

        self._update(device_id, count)
