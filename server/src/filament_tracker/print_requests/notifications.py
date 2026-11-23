"""The notifications print requests send: Request update to the requester when a move
notifies them (the pipeline's `emails_requester`), New photo to the requester when photos are
added later, and New request to Editors and Admins when a request is submitted. Each is about
the request's page.

Who gets each, on each channel, is the notification resolver's to say
(notifications/recipients.py): it applies the role, the person's notification settings, a
disabled account and that no one is told about what they did themselves.

The Done email shows the photos saved with the move, and a photo added later tells the
requester "New photo of your print"; each email shows the photos as inline images in the
HTML part, from their email copies. On a phone, each shows the first of those photos, which
the phone downloads under the API path named here.
"""

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import NotificationKind, Priority, RequestStatus
from filament_tracker.notifications.notification import Notification
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
# Where a photo is served (api/request_photos.py), only to those who can see its request.
PHOTO_PATH = "/api/v1/requests/{request_id}/photos/{photo_id}"
PRIORITY_LABELS = {
    Priority.URGENT: "Urgent",
    Priority.NORMAL: "Normal",
    Priority.NO_RUSH: "No rush",
}


def request_moved(
    moved: Moved, photos: Sequence[bytes] = (), first_photo: UUID | None = None
) -> list[Notification]:
    """The requester's Request update about a move, if the move notifies them, showing
    `photos` (the email copies of those saved with the move) in the email, and the first of
    them, `first_photo`, on a phone."""
    request = moved.request
    if not moved.move.emails_requester:
        return []
    subject, sentence = MOVE_WORDING[moved.move.to_status]
    if moved.then is not None:
        sentence = f"{sentence} {THEN_WORDING[moved.then]}"
    label = "Reason" if moved.move.needs_reason else "Note"
    return [
        _to_requester(
            NotificationKind.REQUEST_UPDATE,
            request,
            moved.user,
            subject=subject.format(title=_one_line(request.title)),
            sentence=sentence.format(title=request.title),
            details=((label, moved.note),) if moved.note else (),
            photos=tuple(photos),
            first_photo=first_photo,
        )
    ]


def new_photos(
    request: PrintRequest,
    user: User | None,
    photos: Sequence[bytes],
    first_photo: UUID | None = None,
) -> list[Notification]:
    """The requester's New photo about photos `user` added after the Done move, showing
    their email copies in the email, and the first of them, `first_photo`, on a phone."""
    if not photos:
        return []
    return [
        _to_requester(
            NotificationKind.NEW_PHOTO,
            request,
            user,
            subject=NEW_PHOTO_SUBJECT.format(title=_one_line(request.title)),
            sentence=NEW_PHOTO_SENTENCE.format(title=request.title),
            photos=tuple(photos),
            first_photo=first_photo,
        )
    ]


def new_request(request: PrintRequest) -> list[Notification]:
    """New request, to the Editors and Admins the resolver tells, which is never its
    requester."""
    requester = request.requester.username
    details = [("Priority", PRIORITY_LABELS[request.priority])]
    if request.needed_by is not None:
        details.append(("Needed by", _day(request.needed_by)))
    return [
        Notification(
            NotificationKind.NEW_REQUEST,
            subject=NEW_REQUEST_SUBJECT.format(requester=requester, title=_one_line(request.title)),
            sentence=NEW_REQUEST_SENTENCE.format(requester=requester, title=request.title),
            path=_path(request),
            link_text=OPEN,
            details=tuple(details),
            actor=request.requester,
        )
    ]


def _to_requester(
    kind: NotificationKind,
    request: PrintRequest,
    actor: User | None,
    *,
    subject: str,
    sentence: str,
    details: tuple[tuple[str, str], ...] = (),
    photos: tuple[bytes, ...] = (),
    first_photo: UUID | None = None,
) -> Notification:
    """A notification only the requester may be told."""
    return Notification(
        kind,
        subject=subject,
        sentence=sentence,
        path=_path(request),
        link_text=OPEN,
        details=details,
        photos=photos,
        photo=None
        if first_photo is None
        else PHOTO_PATH.format(request_id=request.id, photo_id=first_photo),
        actor=actor,
        among=(request.requester,),
        have_requests=True,
    )


def _path(request: PrintRequest) -> str:
    return f"/requests/{request.id}"


def _one_line(text: str) -> str:
    """Text for a header, which can't hold a line break."""
    return " ".join(text.split())


def _day(day: date) -> str:
    """'4 Dec 2026', as the web app shows dates."""
    return f"{day.day} {day:%b %Y}"
