"""Who may do what with print requests (ADR-0017).

Requester is checked apart from the role and never passes a role check. Editors and Admins
see every request and change priorities; anyone else sees only their own requests, which
stay readable whatever their Requester setting. Another user's request reads as not found,
so its existence isn't revealed.
"""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import Role
from filament_tracker.print_requests.photos import PHOTO_STATUSES
from filament_tracker.print_requests.pipeline import Mover


def has_requests(session: Session, user: User) -> bool:
    return bool(session.scalar(select(exists().where(PrintRequest.requester_id == user.id))))


def sees_every_request(principal: Principal) -> bool:
    role = principal.role
    return principal.device is None and role is not None and role.allows(Role.EDITOR)


def may_open_requests(session: Session, principal: Principal) -> bool:
    """The Requests page is theirs: an Editor or Admin, a Requester, or anyone who has made
    a request."""
    if sees_every_request(principal):
        return True
    user = principal.user
    return user is not None and (user.requester or has_requests(session, user))


def may_see(principal: Principal, request: PrintRequest) -> bool:
    if sees_every_request(principal):
        return True
    return principal.user is not None and request.requester_id == principal.user.id


def movers(principal: Principal, request: PrintRequest) -> set[Mover]:
    """Who the caller moves a request as: an Admin, its requester, both or neither. Owning
    the request is what counts, not holding Requester (ADR-0017)."""
    found = set()
    role = principal.role
    if principal.device is None and role is not None and role.allows(Role.ADMIN):
        found.add(Mover.ADMIN)
    if principal.user is not None and request.requester_id == principal.user.id:
        found.add(Mover.REQUESTER)
    return found


def may_change_photos(principal: Principal, request: PrintRequest) -> bool:
    """A signed-in Admin adds and removes photos while the request is Done or Picked Up.
    Tokens act for no one, and a photo records who uploaded it."""
    return (
        principal.user is not None
        and Mover.ADMIN in movers(principal, request)
        and request.status in PHOTO_STATUSES
    )
