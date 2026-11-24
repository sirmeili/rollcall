"""Submitting and editing print requests, and changing their priority. Each writes one
request history entry.

Only a Requester submits. Only the request's own requester edits it, while it is Submitted
and while they still hold Requester; Editors and Admins change the priority of any open
request, and nothing else. Status changes are the pipeline's (pipeline.py). A replaced or
removed model file is deleted once the change is saved (by the caller, after its commit).
"""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.request_models import (
    FilamentChoice,
    PrintRequest,
    RequestHistory,
    RequestUpload,
)
from filament_tracker.domain.enums import HistoryKind, Priority, RequestStatus
from filament_tracker.print_requests.choices import choice_key, make_choices
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.rules import (
    CHOICES,
    FILE,
    LINK,
    NEEDED_BY,
    NOTES,
    PRIORITY,
    QUANTITY,
    TITLE,
    RequestFields,
    check,
)

# How an edit's changed fields are named in the request history.
FILAMENT = "filament"

NOT_A_REQUESTER = "You can no longer submit or edit print requests."
NOT_SUBMITTED = "Only a Submitted request can be edited."
NOT_YOURS = "Only the requester can edit a request."
UPLOAD_GONE = "That file's upload wasn't found. Upload it again."
CLOSED = "A closed request's priority can't be changed."


@dataclass(frozen=True)
class Saved:
    request: PrintRequest
    # A model file that the change replaced or removed, to delete once it is committed.
    old_file: str | None = None


def _upload(session: Session, fields: RequestFields, user: User) -> RequestUpload | None:
    if fields.upload_id is None:
        return None
    upload = session.get(RequestUpload, fields.upload_id)
    if upload is None or upload.user_id != user.id:
        raise Refused.invalid({FILE: UPLOAD_GONE})
    return upload


def _take_file(request: PrintRequest, upload: RequestUpload, session: Session) -> None:
    request.file_stored_name = upload.stored_name
    request.file_name = upload.file_name
    request.file_size = upload.size
    request.file_sha256 = upload.sha256
    request.file_kind = upload.kind
    session.delete(upload)


def _drop_file(request: PrintRequest) -> None:
    request.file_stored_name = None
    request.file_name = None
    request.file_size = None
    request.file_sha256 = None
    request.file_kind = None


def _validate(
    session: Session,
    request: PrintRequest | None,
    fields: RequestFields,
    upload: RequestUpload | None,
    *,
    today: date,
    file_on_disk: bool = False,
) -> list[FilamentChoice]:
    """The choices to save; Refused with every mistake if anything is wrong. A kept file
    counts as the model only while it is still on disk."""
    keeps_file = (
        request is not None
        and request.file_stored_name is not None
        and not fields.remove_file
        and file_on_disk
    )
    problems = check(fields, today=today, has_file=upload is not None or keeps_file)
    choices, choice_problem = make_choices(
        session, fields.choices, request.choices if request is not None else []
    )
    if choice_problem:
        problems[CHOICES] = choice_problem
    if problems:
        raise Refused.invalid(problems)
    return choices


def submit(
    session: Session, user: User, fields: RequestFields, *, today: date, now: datetime
) -> PrintRequest:
    if not user.requester:
        raise Refused.forbidden(NOT_A_REQUESTER)
    fields = fields.cleaned()
    upload = _upload(session, fields, user)
    choices = _validate(session, None, fields, upload, today=today)
    request = PrintRequest(
        requester=user,
        title=fields.title,
        notes=fields.notes,
        quantity=fields.quantity,
        needed_by=fields.needed_by,
        priority=fields.priority,
        link=fields.link,
        status=RequestStatus.SUBMITTED,
        choices=choices,
        created_at=now,
        updated_at=now,
    )
    if upload is not None:
        _take_file(request, upload, session)
    session.add(request)
    session.add(RequestHistory(request=request, kind=HistoryKind.SUBMITTED, user=user, at=now))
    return request


def _changed(
    request: PrintRequest, fields: RequestFields, choices: list[FilamentChoice]
) -> list[str]:
    changed = [
        name
        for name, old, new in (
            (TITLE, request.title, fields.title),
            (QUANTITY, request.quantity, fields.quantity),
            (NEEDED_BY, request.needed_by, fields.needed_by),
            (PRIORITY, request.priority, fields.priority),
            (LINK, request.link, fields.link),
            (NOTES, request.notes, fields.notes),
        )
        if old != new
    ]
    if fields.upload_id is not None or (fields.remove_file and request.file_stored_name):
        changed.append(FILE)
    before = [(choice_key(c), c.note) for c in request.choices]
    after = [(choice_key(c), c.note) for c in choices]
    if before != after:
        changed.append(FILAMENT)
    return changed


def why_not_editable(request: PrintRequest, user: User) -> str | None:
    """Why the user may not edit the request, or None when they may: only its requester,
    while they are still a Requester and it is Submitted."""
    if request.requester_id != user.id:
        return NOT_YOURS
    if not user.requester:
        return NOT_A_REQUESTER
    if request.status != RequestStatus.SUBMITTED:
        return NOT_SUBMITTED
    return None


def edit(
    session: Session,
    request: PrintRequest,
    user: User,
    fields: RequestFields,
    *,
    today: date,
    now: datetime,
    file_on_disk: bool,
) -> Saved:
    """Save an edit by the request's requester, held to the rules of a new request. An edit
    that changes nothing writes no history entry. file_on_disk: the request's file is still
    on disk."""
    reason = why_not_editable(request, user)
    if reason is not None:
        raise Refused.forbidden(reason)
    fields = fields.cleaned()
    upload = _upload(session, fields, user)
    choices = _validate(session, request, fields, upload, today=today, file_on_disk=file_on_disk)
    changed = _changed(request, fields, choices)
    if not changed:
        return Saved(request)
    old_file = None
    if upload is not None or fields.remove_file:
        old_file = request.file_stored_name
        _drop_file(request)
    if upload is not None:
        _take_file(request, upload, session)
    request.title = fields.title
    request.notes = fields.notes
    request.quantity = fields.quantity
    request.needed_by = fields.needed_by
    request.priority = fields.priority
    request.link = fields.link
    if FILAMENT in changed:
        request.choices = choices
    request.updated_at = now
    session.add(
        RequestHistory(request=request, kind=HistoryKind.EDITED, user=user, at=now, fields=changed)
    )
    return Saved(request, old_file)


def change_priority(
    request: PrintRequest, user: User | None, priority: Priority, *, now: datetime
) -> None:
    """An Editor's or Admin's triage, while the request is open. The same priority again
    changes nothing."""
    if request.status.closed:
        raise Refused.forbidden(CLOSED)
    if priority == request.priority:
        return
    request.history.append(
        RequestHistory(
            kind=HistoryKind.PRIORITY_CHANGED,
            user=user,
            at=now,
            from_value=request.priority.value,
            to_value=priority.value,
        )
    )
    request.priority = priority
    request.updated_at = now


def submitted_count(session: Session) -> int:
    query = (
        select(func.count())
        .select_from(PrintRequest)
        .where(PrintRequest.status == RequestStatus.SUBMITTED)
    )
    return session.scalar(query) or 0
