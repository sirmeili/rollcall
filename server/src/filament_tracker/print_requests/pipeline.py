"""The request pipeline: every move a print request may make between request statuses, who
may make it, whether it needs a reason, and whether it emails the requester.

This is the only place that changes a request's status. The API, the detail page's buttons
and later automatic moves (from filament holds, #77, and the printer, #80) all go through
`allowed_moves` and `make_move`; a new move is a new row in `PIPELINE`, and an automatic one
is made by a new kind of mover with no user.

A move names the status it expects the request to be in, so a move made on a stale page is
refused rather than made twice. Each move writes one `status_changed` history entry with the
from and to status, the user, the time and the note or reason.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest, RequestHistory
from filament_tracker.domain.enums import HistoryKind, RequestStatus
from filament_tracker.print_requests.rules import Problems

NOTE_MAX = 500
NOTE = "note"

STALE = "This request has changed. Reload to see it."
NOT_YOURS_TO_MOVE = "You can't move this request to that status."
REASON_NEEDED = "Give a reason."
NOTE_TOO_LONG = f"Keep it to {NOTE_MAX} characters."


class Mover(StrEnum):
    """Who makes a move."""

    ADMIN = "admin"
    # The request's own requester, whether or not they still hold Requester (ADR-0017).
    REQUESTER = "requester"


class Note(StrEnum):
    """What a move asks for alongside it."""

    # A note, which may be left empty.
    OPTIONAL = "optional"
    # A reason, which may not be empty.
    REASON = "reason"


@dataclass(frozen=True)
class Move:
    from_status: RequestStatus
    to_status: RequestStatus
    by: Mover
    note: Note
    emails_requester: bool
    # What an Admin moving their own request is asked for instead; no one is emailed then.
    owner_note: Note | None = None

    @property
    def needs_reason(self) -> bool:
        return self.note is Note.REASON


S = RequestStatus

# In the order the detail page offers them, the main next step first.
PIPELINE: tuple[Move, ...] = (
    Move(S.SUBMITTED, S.APPROVED, Mover.ADMIN, Note.OPTIONAL, emails_requester=True),
    Move(S.SUBMITTED, S.REJECTED, Mover.ADMIN, Note.REASON, emails_requester=True),
    Move(S.APPROVED, S.QUEUED, Mover.ADMIN, Note.OPTIONAL, emails_requester=False),
    Move(S.APPROVED, S.WAITING_ON_FILAMENT, Mover.ADMIN, Note.OPTIONAL, emails_requester=True),
    Move(S.WAITING_ON_FILAMENT, S.QUEUED, Mover.ADMIN, Note.OPTIONAL, emails_requester=False),
    Move(S.QUEUED, S.PRINTING, Mover.ADMIN, Note.OPTIONAL, emails_requester=True),
    Move(S.PRINTING, S.DONE, Mover.ADMIN, Note.OPTIONAL, emails_requester=True),
    Move(S.PRINTING, S.FAILED, Mover.ADMIN, Note.OPTIONAL, emails_requester=True),
    # Reprint: another attempt of the same request.
    Move(S.FAILED, S.QUEUED, Mover.ADMIN, Note.OPTIONAL, emails_requester=False),
    Move(S.DONE, S.PICKED_UP, Mover.ADMIN, Note.OPTIONAL, emails_requester=False),
    Move(S.DONE, S.PICKED_UP, Mover.REQUESTER, Note.OPTIONAL, emails_requester=False),
    # Cancel, while the request hasn't started printing; last, so the next steps come first.
    *(
        Move(status, S.CANCELLED, Mover.REQUESTER, Note.OPTIONAL, emails_requester=False)
        for status in (S.SUBMITTED, S.APPROVED, S.WAITING_ON_FILAMENT, S.QUEUED)
    ),
    *(
        Move(
            status,
            S.CANCELLED,
            Mover.ADMIN,
            Note.REASON,
            emails_requester=True,
            owner_note=Note.OPTIONAL,
        )
        for status in (S.SUBMITTED, S.APPROVED, S.WAITING_ON_FILAMENT, S.QUEUED, S.FAILED)
    ),
)


class Stale(Exception):
    """The request is no longer in the status the move expected."""


class NotAMove(Exception):
    """The pipeline has no such move, or none this caller may make."""


@dataclass(frozen=True)
class Moved:
    """A move that was made: which one, by whom (None for a later automatic move), and its
    note or reason, trimmed ("" for none)."""

    request: PrintRequest
    move: Move
    user: User | None
    note: str = ""


def attempt(request: PrintRequest) -> int:
    """Which try at printing this is: 1, plus 1 for each Reprint in its history. There is no
    attempt table or field; a reprinted request stays the same request."""
    return 1 + sum(
        1
        for entry in request.history
        if entry.kind == HistoryKind.STATUS_CHANGED
        and (entry.from_value, entry.to_value) == (S.FAILED.value, S.QUEUED.value)
    )


def allowed_moves(request: PrintRequest, movers: set[Mover]) -> list[Move]:
    """The moves these movers may make from the request's status now, one per status they
    lead to. A mover who is both an Admin and the requester moves as an Admin, asked for the
    move's owner note where it has one."""
    found: dict[RequestStatus, Move] = {}
    for rule in PIPELINE:
        if rule.from_status != request.status or rule.by not in movers:
            continue
        held = found.get(rule.to_status)
        if held is None or (held.by is not Mover.ADMIN and rule.by is Mover.ADMIN):
            found[rule.to_status] = rule
    if Mover.REQUESTER in movers:
        found = {to: _as_owner(rule) for to, rule in found.items()}
    return list(found.values())


def _as_owner(rule: Move) -> Move:
    if rule.by is not Mover.ADMIN or rule.owner_note is None:
        return rule
    return replace(rule, note=rule.owner_note, emails_requester=False)


def clean_note(note: str, rule: Move) -> str:
    """The note trimmed; Problems if it is too long, or empty where a reason is needed."""
    cleaned = note.strip()
    if len(cleaned) > NOTE_MAX:
        raise Problems({NOTE: NOTE_TOO_LONG})
    if rule.needs_reason and not cleaned:
        raise Problems({NOTE: REASON_NEEDED})
    return cleaned


def make_move(
    request: PrintRequest,
    *,
    expected: RequestStatus,
    to_status: RequestStatus,
    movers: set[Mover],
    user: User | None,
    note: str,
    now: datetime,
) -> Moved:
    """Move the request on, or refuse: Stale when it has left `expected`, NotAMove when the
    caller may not make this move, and Problems for the note."""
    if request.status != expected:
        raise Stale(STALE)
    rule = next((m for m in allowed_moves(request, movers) if m.to_status == to_status), None)
    if rule is None:
        raise NotAMove(NOT_YOURS_TO_MOVE)
    cleaned = clean_note(note, rule)
    request.history.append(
        RequestHistory(
            kind=HistoryKind.STATUS_CHANGED,
            user=user,
            at=now,
            from_value=request.status.value,
            to_value=to_status.value,
            note=cleaned or None,
        )
    )
    request.status = to_status
    request.updated_at = now
    return Moved(request, rule, user, cleaned)
