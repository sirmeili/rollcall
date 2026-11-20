"""A mail transport for tests: it records each message instead of sending it, and can be
told to fail."""

import threading
from email.message import EmailMessage

from filament_tracker.mail.transport import MailError, SmtpServer


class FakeOutbox:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.servers: list[SmtpServer] = []
        self.attempts = 0
        self._failures_left = 0
        self._failure = ""
        self._lock = threading.Lock()
        self.delivered = threading.Event()

    def fail(self, times: int = 1_000_000, message: str = "Can't reach the mail server.") -> None:
        """Fail the next `times` sends with `message`."""
        self._failures_left, self._failure = times, message

    def send(self, server: SmtpServer, message: EmailMessage) -> None:
        with self._lock:
            self.attempts += 1
            if self._failures_left:
                self._failures_left -= 1
                raise MailError(self._failure)
            self.sent.append(message)
            self.servers.append(server)
        self.delivered.set()


def text_of(message: EmailMessage) -> str:
    body = message.get_body(("plain",))
    assert body is not None
    return body.get_content()


def html_of(message: EmailMessage) -> str:
    body = message.get_body(("html",))
    assert body is not None
    return body.get_content()
