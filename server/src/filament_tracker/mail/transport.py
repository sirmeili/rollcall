"""The mail transport seam: what the sender hands a built message to.

`create_app` takes one (like `catalog_transport`); it defaults to the SMTP sender, and tests
pass a fake outbox.
"""

from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal, Protocol

from pydantic import SecretStr

Security = Literal["starttls", "tls", "none"]


@dataclass(frozen=True)
class SmtpServer:
    """The saved email settings a message is sent with."""

    host: str
    port: int
    security: Security
    user: str | None
    password: SecretStr | None
    from_address: str | None


class MailError(Exception):
    """A send that failed. The message is safe to show and log: it never holds the
    password, and never repeats the mail server's own text."""


class MailTransport(Protocol):
    def send(self, server: SmtpServer, message: EmailMessage) -> None:
        """Send one message, or raise MailError."""
        ...
