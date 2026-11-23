"""The email channel. Every notification email has the same shape: one sentence saying what
happened, labelled details, a link to the page it is about (built from PUBLIC_URL only) and
the footer saying where to change notification settings. Each goes to a person told by email
who has an address."""

from collections.abc import Iterable, Sequence
from email.utils import make_msgid
from html import escape

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import Channel
from filament_tracker.mail.message import Email, InlineImage
from filament_tracker.notifications.notification import Notification

FOOTER = "You can change these on your Account page."


def link(public_url: str | None, path: str) -> str | None:
    """The web app's page at `path` ("/settings"), under PUBLIC_URL; None without it, so the
    email has no link. Never built from an incoming request's Host header."""
    return None if public_url is None else f"{public_url}{path}"


def emails(
    session: Session, notifications: Iterable[Notification], public_url: str | None
) -> list[Email]:
    """An email about each notification to each person told about it by email who has an
    address."""
    return [
        compose(
            user.email,
            subject=n.subject,
            sentence=n.sentence,
            details=n.details,
            link=link(public_url, n.path),
            link_text=n.link_text,
            photos=n.email_photos,
        )
        for n in notifications
        for user in n.told(session, Channel.EMAIL)
        if user.email is not None
    ]


def compose(
    to: str,
    *,
    subject: str,
    sentence: str,
    details: Iterable[tuple[str, str]] = (),
    link: str | None,
    link_text: str,
    photos: Sequence[bytes] = (),
) -> Email:
    """The sentence, the labelled details, the link and the footer, as text and HTML, with
    the photos shown inline in the HTML after the details."""
    details = list(details)
    text = [sentence]
    html = [f"<p>{escape(sentence)}</p>"]
    if details:
        text.append("\n".join(f"{label}: {value}" for label, value in details))
        lines = (f"<strong>{escape(label)}:</strong> {escape(value)}" for label, value in details)
        html.append(f"<p>{'<br>'.join(lines)}</p>")
    images = tuple(InlineImage(make_msgid("photo")[1:-1], photo) for photo in photos)
    for number, image in enumerate(images, 1):
        html.append(
            f'<p><img src="cid:{escape(image.content_id)}" alt="Photo {number} of your print"'
            ' style="max-width: 100%; height: auto;"></p>'
        )
    if link is not None:
        text.append(f"{link_text}: {link}")
        html.append(f'<p><a href="{escape(link)}">{escape(link_text)}</a></p>')
    text.append(FOOTER)
    html.append(f"<p>{escape(FOOTER)}</p>")
    return Email(
        to=to,
        subject=subject,
        text="\n\n".join(text) + "\n",
        html=f"<!doctype html><html><body>{''.join(html)}</body></html>",
        images=images,
    )
