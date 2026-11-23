"""The emails print requests send: Request update to the requester when a move emails them
(the pipeline's `emails_requester`), New photo to the requester when photos are added
later, and New request to Editors and Admins when a request is submitted.

Who gets each is the notification resolver's to say (notifications/recipients.py): it
applies the role, the person's notification settings, a disabled account and that no one is
told about what they did themselves. Each goes only to a person with an address.

Links use PUBLIC_URL only, never the incoming request's Host header; without it, emails have
no link. The Done email shows the photos saved with the
move, and a photo added later emails the requester "New photo of your print"; each shows
the photos as inline images in the HTML part, from their email copies.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import NotificationKind, Priority, RequestStatus
from filament_tracker.mail.message import Email
from filament_tracker.notifications.email import compose
from filament_tracker.notifications.recipients import email_recipients
from filament_tracker.print_requests.pipeline import Moved

# The subject and the one sentence saying what happened, for each status a move that
# emails the requester leads to.
MOVE_WORDING: dict[RequestStatus, tuple[str, str]] = {
    RequestStatus.APPROVED: (
        "Your print request was approved: {title}",
        'Your print request "{title}" was approved.',
    ),
    RequestStatus.REJECTED: (
        "Your print request was rejected: {title}",
        'Your print request "{title}" was rejected.',
    ),
    RequestStatus.WAITING_ON_FILAMENT: (
        "Your print request is waiting on filament: {title}",
        'Your print request "{title}" is waiting on filament.',
    ),
    RequestStatus.PRINTING: (
        "Your print request is printing: {title}",
        'Your print request "{title}" is printing.',
    ),
    RequestStatus.DONE: ("Your print is done: {title}", 'Your print "{title}" is done.'),
    RequestStatus.FAILED: ("Your print failed: {title}", 'Your print "{title}" failed.'),
    RequestStatus.CANCELLED: (
        "Your print request was cancelled: {title}",
        'Your print request "{title}" was cancelled.',
    ),
}
# Added to the Approved email: where the request went straight after.
THEN_WORDING = {
    RequestStatus.QUEUED: "It's queued.",
    RequestStatus.WAITING_ON_FILAMENT: "It's waiting on filament.",
}
NEW_PHOTO_SUBJECT = "New photo of your print: {title}"
NEW_PHOTO_SENTENCE = 'A new photo of your print "{title}" was added.'
NEW_REQUEST_SUBJECT = "New print request from {requester}: {title}"
NEW_REQUEST_SENTENCE = '{requester} submitted a new print request: "{title}".'
OPEN = "Open the request"
PRIORITY_LABELS = {
    Priority.URGENT: "Urgent",
    Priority.NORMAL: "Normal",
    Priority.NO_RUSH: "No rush",
}


def move_emails(
    session: Session, moved: Moved, public_url: str | None, photos: Sequence[bytes] = ()
) -> list[Email]:
    """The requester's Request update email about a move, if the move emails them and the
    resolver tells them, showing `photos` (the email copies of those saved with the move)."""
    request = moved.request
    if not moved.move.emails_requester:
        return []
    to = _requester(session, NotificationKind.REQUEST_UPDATE, request, moved.user)
    if to is None:
        return []
    subject, sentence = MOVE_WORDING[moved.move.to_status]
    if moved.then is not None:
        sentence = f"{sentence} {THEN_WORDING[moved.then]}"
    label = "Reason" if moved.move.needs_reason else "Note"
    return [
        compose(
            to,
            subject=subject.format(title=_one_line(request.title)),
            sentence=sentence.format(title=request.title),
            details=[(label, moved.note)] if moved.note else [],
            link=_link(request, public_url),
            link_text=OPEN,
            photos=photos,
        )
    ]


def new_photo_emails(
    session: Session,
    request: PrintRequest,
    user: User | None,
    photos: Sequence[bytes],
    public_url: str | None,
) -> list[Email]:
    """The requester's New photo email about photos `user` added after the Done move,
    showing their email copies, if the resolver tells them."""
    if not photos:
        return []
    to = _requester(session, NotificationKind.NEW_PHOTO, request, user)
    if to is None:
        return []
    return [
        compose(
            to,
            subject=NEW_PHOTO_SUBJECT.format(title=_one_line(request.title)),
            sentence=NEW_PHOTO_SENTENCE.format(title=request.title),
            link=_link(request, public_url),
            link_text=OPEN,
            photos=photos,
        )
    ]


def new_request_emails(
    session: Session, request: PrintRequest, public_url: str | None
) -> list[Email]:
    """A New request email to each Editor and Admin the resolver tells, which is never its
    requester."""
    requester = request.requester.username
    details = [("Priority", PRIORITY_LABELS[request.priority])]
    if request.needed_by is not None:
        details.append(("Needed by", _day(request.needed_by)))
    return [
        compose(
            to,
            subject=NEW_REQUEST_SUBJECT.format(requester=requester, title=_one_line(request.title)),
            sentence=NEW_REQUEST_SENTENCE.format(requester=requester, title=request.title),
            details=details,
            link=_link(request, public_url),
            link_text=OPEN,
        )
        for to in email_recipients(session, NotificationKind.NEW_REQUEST, actor=request.requester)
    ]


def _requester(
    session: Session, kind: NotificationKind, request: PrintRequest, actor: User | None
) -> str | None:
    """The requester's address, if the resolver tells them about `kind`; None otherwise."""
    found = email_recipients(session, kind, actor=actor, among=[request.requester])
    return found[0] if found else None


def _link(request: PrintRequest, public_url: str | None) -> str | None:
    return None if public_url is None else f"{public_url}/requests/{request.id}"


def _one_line(text: str) -> str:
    """Text for a header, which can't hold a line break."""
    return " ".join(text.split())


def _day(day: date) -> str:
    """'4 Dec 2026', as the web app shows dates."""
    return f"{day.day} {day:%b %Y}"
