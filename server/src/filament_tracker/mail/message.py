"""Built emails: every one is sent as plain text and HTML."""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str


def mime_message(email: Email, from_address: str) -> EmailMessage:
    """The message to send: plain text with an HTML alternative."""
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = email.to
    message["Subject"] = email.subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=_domain(from_address))
    message.set_content(email.text)
    message.add_alternative(email.html, subtype="html")
    return message


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].rstrip(">").strip() or "rollcall"
