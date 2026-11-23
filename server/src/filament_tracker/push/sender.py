"""The background phone sender: Web Pushes are handed over after the work commits, so a move
or a save never waits for a push service or fails because of it.

Each push names a phone (its device) and carries the payload; the phone's endpoint is read
when it is sent, so a phone removed, revoked or disabled in the meantime gets nothing.

- A 404 or 410 means the phone's endpoint is gone (the app uninstalled, or its data cleared):
  it is dropped at once.
- Any other failure (a timeout, a 5xx, a 429) is retried 3 times over about 15 minutes, then
  given up and counted on the endpoint. An endpoint failing with no success in 30 days is
  dropped.

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
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.db.types import utcnow
from filament_tracker.push.keys import VapidKeys
from filament_tracker.push.transport import PushError, PushTransport
from filament_tracker.push.webpush import PushMessage, Subscription, web_push

logger = logging.getLogger(__name__)

# The waits before each retry: 1, 4 and 10 minutes, so 15 minutes in all.
RETRIES = (60.0, 240.0, 600.0)
# An endpoint with no success for this long is dropped when a push to it is given up.
STALE_AFTER = timedelta(days=30)
STOP_TIMEOUT = 5.0
GONE = {404, 410}
UNEXPECTED = "The phone notification couldn't be sent."


@dataclass(frozen=True)
class Push:
    """A phone notification for one phone."""

    device_id: str
    payload: bytes


class Outcome(StrEnum):
    SENT = "sent"
    # The endpoint is gone, and was dropped.
    GONE = "gone"
    FAILED = "failed"
    # The phone has no endpoint, or may no longer get phone notifications.
    NOWHERE = "nowhere"


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    # Safe to show: never the push service's own text.
    message: str = ""


@dataclass(order=True)
class _Pending:
    due: float
    order: int
    push: Push
    attempt: int = 0


def reachable(endpoint: PushEndpoint) -> bool:
    """Whether the endpoint's phone may get phone notifications: a user's phone, not
    revoked, whose user isn't disabled. A shared phone never does."""
    device = endpoint.device
    return (
        device.revoked_at is None and device.user is not None and device.user.disabled_at is None
    )


class PushSender:
    def __init__(
        self,
        transport: PushTransport,
        sessions: sessionmaker[Session],
        keys: VapidKeys,
        *,
        retries: tuple[float, ...] = RETRIES,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._transport = transport
        self._sessions = sessions
        self._keys = keys
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
        if result.outcome != Outcome.FAILED:
            return
        if item.attempt < len(self._retries):
            with self._wake:
                item.due = time.monotonic() + self._retries[item.attempt]
                item.attempt += 1
                heapq.heappush(self._pending, item)
                self._wake.notify_all()
            return
        self._give_up(item.push.device_id, result.message, item.attempt + 1)

    def _send(self, push: Push) -> Result:
        try:
            message = self._message(push)
            if message is None:
                return Result(Outcome.NOWHERE)
            status = self._transport.post(message)
        except PushError as error:
            return Result(Outcome.FAILED, str(error))
        except Exception as error:
            # Only the type: an unexpected error's text could hold anything.
            logger.warning("phone notification: unexpected %s while sending", type(error).__name__)
            return Result(Outcome.FAILED, UNEXPECTED)
        if 200 <= status < 300:
            self._update(push.device_id, self._succeeded)
            return Result(Outcome.SENT)
        if status in GONE:
            self._update(push.device_id, self._drop)
            logger.info("phone %s's push endpoint is gone, so it was dropped", push.device_id)
            return Result(Outcome.GONE, "This phone's push endpoint is gone.")
        return Result(Outcome.FAILED, f"The push service answered {status}.")

    def _message(self, push: Push) -> PushMessage | None:
        with self._sessions() as session:
            endpoint = session.get(PushEndpoint, push.device_id)
            if endpoint is None or not reachable(endpoint):
                return None
            to = Subscription(endpoint.endpoint, endpoint.p256dh or "", endpoint.auth or "")
        return web_push(to, push.payload, self._keys)

    def _update(self, device_id: str, change: Callable[[Session, PushEndpoint], None]) -> None:
        with self._sessions() as session:
            endpoint = session.get(PushEndpoint, device_id)
            if endpoint is not None:
                change(session, endpoint)
                session.commit()

    def _succeeded(self, session: Session, endpoint: PushEndpoint) -> None:
        endpoint.last_success_at = self._clock()
        endpoint.failures = 0

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
            since = endpoint.last_success_at or endpoint.registered_at
            if self._clock() - since >= STALE_AFTER:
                session.delete(endpoint)
                logger.info("phone %s had no success in 30 days, so it was dropped", device_id)

        self._update(device_id, count)
