"""The background sender: built emails are handed over after the work commits, so a move
or a save never waits for email or fails because of it.

A failed send is retried 3 times over about 15 minutes, then logged and dropped. There is
no stored outbox, so emails still waiting are lost on a restart. The last success and the
last failure are kept in memory for the Settings page.
"""

import heapq
import itertools
import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from filament_tracker.db.types import utcnow
from filament_tracker.mail.message import Email, mime_message
from filament_tracker.mail.transport import MailError, MailTransport, SmtpServer

logger = logging.getLogger(__name__)

# The waits before each retry: 1, 4 and 10 minutes, so 15 minutes in all.
RETRIES = (60.0, 240.0, 600.0)
STOP_TIMEOUT = 5.0
NO_FROM = "No from address is set."
UNEXPECTED = "The email couldn't be sent."
BAD_SETTINGS = "The email settings couldn't be read."


@dataclass(frozen=True)
class Failure:
    at: datetime
    message: str


@dataclass(order=True)
class _Pending:
    due: float
    order: int
    email: Email
    attempt: int = 0


class MailSender:
    def __init__(
        self,
        transport: MailTransport,
        server: Callable[[], SmtpServer | None],
        *,
        retries: tuple[float, ...] = RETRIES,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._transport = transport
        self._server = server
        self._retries = retries
        self._clock = clock
        self._pending: list[_Pending] = []
        self._order = itertools.count()
        self._wake = threading.Condition()
        self._stopping = False
        self._thread: threading.Thread | None = None
        self.last_success: datetime | None = None
        self.last_failure: Failure | None = None

    @property
    def on(self) -> bool:
        """Whether email is set up: an SMTP host is saved."""
        return self._server() is not None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="mail-sender", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._wake:
            self._stopping = True
            self._wake.notify_all()
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT)

    def send_later(self, emails: Iterable[Email]) -> None:
        """Queue emails to send in the background. Returns at once."""
        with self._wake:
            for email in emails:
                heapq.heappush(self._pending, _Pending(time.monotonic(), next(self._order), email))
            self._wake.notify_all()

    def send_now(self, email: Email) -> None:
        """Send one email and wait for the result, with no retries. Raises MailError; email
        being off is an error here too."""
        server = self._settings()
        if server is None:
            raise MailError("Email is off: no SMTP host is set.")
        self._deliver(server, email)

    def _run(self) -> None:
        while True:
            with self._wake:
                item = self._next()
                if item is None:
                    return
            self._attempt(item)

    def _next(self) -> _Pending | None:
        """The next email that is due, waiting for one; None once stopping."""
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
        try:
            server = self._settings()
            if server is None:
                logger.info("email is off, so an email was dropped")
                return
            self._deliver(server, item.email)
        except MailError as error:
            if item.attempt < len(self._retries):
                with self._wake:
                    item.due = time.monotonic() + self._retries[item.attempt]
                    item.attempt += 1
                    heapq.heappush(self._pending, item)
                    self._wake.notify_all()
                return
            logger.warning("an email was dropped after %d tries: %s", item.attempt + 1, error)

    def _settings(self) -> SmtpServer | None:
        """The saved SMTP server, or None when email is off. Raises MailError, recorded as
        the last failure, when the settings can't be read."""
        try:
            return self._server()
        except Exception as error:
            # Only the type: the error's text could hold a setting's value.
            logger.warning("email: unexpected %s while reading the settings", type(error).__name__)
            self.last_failure = Failure(self._clock(), BAD_SETTINGS)
            raise MailError(BAD_SETTINGS) from None

    def _deliver(self, server: SmtpServer, email: Email) -> None:
        try:
            if not server.from_address:
                raise MailError(NO_FROM)
            self._transport.send(server, mime_message(email, server.from_address))
        except MailError as error:
            self.last_failure = Failure(self._clock(), str(error))
            raise
        except Exception as error:
            # Only the type: an unexpected error's text could hold anything.
            logger.warning("email: unexpected %s while sending", type(error).__name__)
            self.last_failure = Failure(self._clock(), UNEXPECTED)
            raise MailError(UNEXPECTED) from None
        self.last_success = self._clock()
