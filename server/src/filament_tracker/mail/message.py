"""Built emails: every one is sent as plain text and HTML, and the HTML can show images
attached inline."""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


@dataclass(frozen=True)
class InlineImage:
    """A JPEG the HTML shows with `<img src="cid:{content_id}">`."""

    content_id: str
    jpeg: bytes


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str
    images: tuple[InlineImage, ...] = ()


def mime_message(email: Email, from_address: str) -> EmailMessage:
    """The message to send: plain text with an HTML alternative, and the HTML's images
    attached inline beside it."""
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = email.to
    message["Subject"] = email.subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=_domain(from_address))
    message.set_content(email.text)
    message.add_alternative(email.html, subtype="html")
    if email.images:
        html = message.get_body(("html",))
        assert html is not None  # noqa: S101 - the alternative just added
        for image in email.images:
            html.add_related(
                image.jpeg, "image", "jpeg", cid=f"<{image.content_id}>", disposition="inline"
            )
    return message


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].rstrip(">").strip() or "rollcall"
