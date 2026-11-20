"""The emails print requests send: to the requester when a move emails them (the pipeline's
`emails_requester`), and to every other Admin when a request is submitted.

Each is sent only to a person with an address, the matching Account switch on, and an
account that isn't disabled. Links use PUBLIC_URL only, never the incoming request's Host
header; without it, emails have no link. The Done email shows the photos saved with the
move, and a photo added later emails the requester "New photo of your print"; each shows
the photos as inline images in the HTML part, from their email copies.
"""

from collections.abc import Iterable, Sequence
from datetime import date
from email.utils import make_msgid
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import Priority, RequestStatus, Role
from filament_tracker.mail.message import Email, InlineImage
from filament_tracker.print_requests.pipeline import Moved

S = RequestStatus

# The subject and the one sentence saying what happened, for each status a move that
# emails the requester leads to.
MOVE_WORDING: dict[RequestStatus, tuple[str, str]] = {
    S.APPROVED: (
        "Your print request was approved: {title}",
        'Your print request "{title}" was approved.',
    ),
    S.REJECTED: (
        "Your print request was rejected: {title}",
        'Your print request "{title}" was rejected.',
    ),
    S.WAITING_ON_FILAMENT: (
        "Your print request is waiting on filament: {title}",
        'Your print request "{title}" is waiting on filament.',
    ),
    S.PRINTING: (
        "Your print request is printing: {title}",
        'Your print request "{title}" is printing.',
    ),
    S.DONE: ("Your print is done: {title}", 'Your print "{title}" is done.'),
    S.FAILED: ("Your print failed: {title}", 'Your print "{title}" failed.'),
    S.CANCELLED: (
        "Your print request was cancelled: {title}",
        'Your print request "{title}" was cancelled.',
    ),
}
NEW_PHOTO_SUBJECT = "New photo of your print: {title}"
NEW_PHOTO_SENTENCE = 'A new photo of your print "{title}" was added.'
NEW_REQUEST_SUBJECT = "New print request from {requester}: {title}"
NEW_REQUEST_SENTENCE = '{requester} submitted a new print request: "{title}".'
OPEN = "Open the request"
FOOTER = "You can turn these emails off on your Account page."
PRIORITY_LABELS = {
    Priority.URGENT: "Urgent",
    Priority.NORMAL: "Normal",
    Priority.NO_RUSH: "No rush",
}


def move_emails(moved: Moved, public_url: str | None, photos: Sequence[bytes] = ()) -> list[Email]:
    """The requester's email about a move, if the move emails them and they want it, showing
    `photos` (the email copies of those saved with the move)."""
    if not moved.move.emails_requester:
        return []
    request = moved.request
    to = _address(request.requester, request.requester.email_on_request_change)
    if to is None:
        return []
    subject, sentence = MOVE_WORDING[moved.move.to_status]
    label = "Reason" if moved.move.needs_reason else "Note"
    return [
        _compose(
            to,
            subject.format(title=_one_line(request.title)),
            sentence.format(title=request.title),
            [(label, moved.note)] if moved.note else [],
            _link(request, public_url),
            FOOTER,
            photos,
        )
    ]


def new_photo_emails(
    request: PrintRequest, user: User | None, photos: Sequence[bytes], public_url: str | None
) -> list[Email]:
    """The requester's email about photos `user` added after the Done move, showing their
    email copies, unless the requester added them or doesn't want it."""
    requester = request.requester
    if not photos or (user is not None and user.id == requester.id):
        return []
    to = _address(requester, requester.email_on_request_change)
    if to is None:
        return []
    return [
        _compose(
            to,
            NEW_PHOTO_SUBJECT.format(title=_one_line(request.title)),
            NEW_PHOTO_SENTENCE.format(title=request.title),
            [],
            _link(request, public_url),
            FOOTER,
            photos,
        )
    ]


def new_request_emails(
    session: Session, request: PrintRequest, public_url: str | None
) -> list[Email]:
    """An email to every Admin who wants one about a new request, other than its requester."""
    admins = session.scalars(
        select(User).where(User.role == Role.ADMIN, User.id != request.requester_id)
    )
    requester = request.requester.username
    details = [("Priority", PRIORITY_LABELS[request.priority])]
    if request.needed_by is not None:
        details.append(("Needed by", _day(request.needed_by)))
    emails = []
    for user in admins:
        to = _address(user, user.email_on_new_request)
        if to is None:
            continue
        emails.append(
            _compose(
                to,
                NEW_REQUEST_SUBJECT.format(requester=requester, title=_one_line(request.title)),
                NEW_REQUEST_SENTENCE.format(requester=requester, title=request.title),
                details,
                _link(request, public_url),
                None,
            )
        )
    return emails


def _address(user: User, wants_it: bool) -> str | None:
    """Where to email the user, or None when they have no address, don't want it, or are
    disabled."""
    if not wants_it or user.disabled_at is not None:
        return None
    return user.email


def _link(request: PrintRequest, public_url: str | None) -> str | None:
    return None if public_url is None else f"{public_url}/requests/{request.id}"


def _one_line(text: str) -> str:
    """Text for a header, which can't hold a line break."""
    return " ".join(text.split())


def _day(day: date) -> str:
    """'4 Dec 2026', as the web app shows dates."""
    return f"{day.day} {day:%b %Y}"


def _compose(
    to: str,
    subject: str,
    sentence: str,
    details: Iterable[tuple[str, str]],
    link: str | None,
    footer: str | None,
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
        text.append(f"{OPEN}: {link}")
        html.append(f'<p><a href="{escape(link)}">{OPEN}</a></p>')
    if footer is not None:
        text.append(footer)
        html.append(f"<p>{escape(footer)}</p>")
    return Email(
        to=to,
        subject=subject,
        text="\n\n".join(text) + "\n",
        html=f"<!doctype html><html><body>{''.join(html)}</body></html>",
        images=images,
    )
