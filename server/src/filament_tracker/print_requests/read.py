"""Reading print requests: the Requests list and one request's detail.

The list has two tabs. Active holds every open status, sorted by priority (Urgent, Normal,
No rush), then needed-by date, earliest first with no date last, then oldest first. Closed
holds Picked Up, Rejected and Cancelled, the latest move first. Editors and Admins see every
request, and may narrow the list to some open statuses or to their own requests; anyone else
sees only their own.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import FilamentChoice, PrintRequest
from filament_tracker.domain.enums import HistoryKind, ModelSource, RequestStatus
from filament_tracker.print_requests.access import sees_every_request


def sort_key(request: PrintRequest) -> tuple[int, bool, date, datetime, int]:
    needed = request.needed_by
    return (
        request.priority.rank,
        needed is None,
        needed or date.max,
        request.created_at,
        request.id,
    )


class Tab(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


CLOSED_STATUSES = [status for status in RequestStatus if status.closed]


@dataclass(frozen=True)
class ListFilter:
    tab: Tab = Tab.ACTIVE
    # Open statuses to keep; empty keeps them all. Only Editors and Admins narrow by status.
    statuses: list[RequestStatus] = field(default_factory=list)
    # Only the caller's own requests: what anyone but an Editor or Admin sees anyway.
    mine: bool = False


def last_move_at(request: PrintRequest) -> datetime:
    """When the request last changed status: when it closed, on the Closed tab."""
    moves = [e.at for e in request.history if e.kind is HistoryKind.STATUS_CHANGED]
    return max(moves, default=request.updated_at)


def closed_sort_key(request: PrintRequest) -> tuple[datetime, int]:
    return (last_move_at(request), request.id)


def visible_requests(
    session: Session, principal: Principal, wanted: ListFilter | None = None
) -> list[PrintRequest]:
    wanted = wanted or ListFilter()
    query = select(PrintRequest).options(
        selectinload(PrintRequest.requester),
        selectinload(PrintRequest.choices).selectinload(FilamentChoice.product),
    )
    staff = sees_every_request(principal)
    if not staff or wanted.mine:
        user_id = principal.user.id if principal.user is not None else -1
        query = query.where(PrintRequest.requester_id == user_id)
    if wanted.tab is Tab.CLOSED:
        query = query.where(PrintRequest.status.in_(CLOSED_STATUSES))
        query = query.options(selectinload(PrintRequest.history))
        return sorted(session.scalars(query), key=closed_sort_key, reverse=True)
    query = query.where(PrintRequest.status.not_in(CLOSED_STATUSES))
    if staff and wanted.statuses:
        query = query.where(PrintRequest.status.in_(wanted.statuses))
    return sorted(session.scalars(query), key=sort_key)


def model_source(request: PrintRequest) -> ModelSource:
    """What the request has for its model: a file, a link, both, or only its notes."""
    has_file, has_link = request.file_stored_name is not None, request.link is not None
    if has_file and has_link:
        return ModelSource.BOTH
    if has_file:
        return ModelSource.FILE
    return ModelSource.LINK if has_link else ModelSource.NOTES_ONLY
