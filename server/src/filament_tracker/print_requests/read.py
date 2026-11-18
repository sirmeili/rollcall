"""Reading print requests: the Requests list and one request's detail.

The list is sorted by priority (Urgent, Normal, No rush), then needed-by date, earliest first
with no date last, then oldest first. Editors and Admins see every request; anyone else sees
only their own.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import FilamentChoice, PrintRequest
from filament_tracker.print_requests.access import sees_every_request

FILE = "file"
LINK = "link"
BOTH = "both"
NOTES_ONLY = "notes"


def sort_key(request: PrintRequest) -> tuple[int, bool, date, datetime, int]:
    needed = request.needed_by
    return (
        request.priority.rank,
        needed is None,
        needed or date.max,
        request.created_at,
        request.id,
    )


def visible_requests(session: Session, principal: Principal) -> list[PrintRequest]:
    query = select(PrintRequest).options(
        selectinload(PrintRequest.requester),
        selectinload(PrintRequest.choices).selectinload(FilamentChoice.product),
    )
    if not sees_every_request(principal):
        user_id = principal.user.id if principal.user is not None else -1
        query = query.where(PrintRequest.requester_id == user_id)
    return sorted(session.scalars(query), key=sort_key)


def model_source(request: PrintRequest) -> str:
    """What the request has for its model: a file, a link, both, or only its notes."""
    has_file, has_link = request.file_stored_name is not None, request.link is not None
    if has_file and has_link:
        return BOTH
    if has_file:
        return FILE
    return LINK if has_link else NOTES_ONLY
