"""The checks that run before a request's body is read: one gate for each kind of action.

A caller who fails a gate is refused before anything they sent is looked at. Each action asks
its gate again, then its own rules: whether the caller sees the request, owns it, and its
status.
"""

from collections.abc import Callable
from enum import Enum
from typing import Literal

from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.domain.enums import Role
from filament_tracker.print_requests import photos
from filament_tracker.print_requests.access import changes_holds, is_admin, may_open_requests
from filament_tracker.print_requests.pipeline import NOT_YOURS_TO_MOVE
from filament_tracker.print_requests.service import NOT_A_REQUESTER

NO_ACCESS = "requires Requester or the editor role"
HOLDS_ADMINS_ONLY = "Only a signed-in Admin changes holds."
NO_SCANNERS = "scanners cannot use this endpoint"
NOT_AN_EDITOR = f"requires the {Role.EDITOR.value} role"


class Gate(Enum):
    # May open the Requests pages: an Editor or Admin, a Requester, or anyone with requests.
    OPEN = "open"
    # Submit a request or upload a model file: a signed-in Requester.
    SUBMIT = "submit"
    # Edit a request: a signed-in user who may open the Requests pages.
    EDIT = "edit"
    # Move a request: a person who may open the Requests pages, or an Admin.
    MOVE = "move"
    # Change a request's priority: an Editor.
    PRIORITY = "priority"
    # Count the Submitted requests: an Editor.
    COUNT = "count"
    # Change a request's holds: a signed-in Admin.
    HOLDS = "holds"
    # Upload, add or remove photos: a signed-in Admin.
    PHOTOS = "photos"


# The gates that let only signed-in people through, so a caller who passes one has a user.
PersonGate = Literal[Gate.SUBMIT, Gate.EDIT, Gate.HOLDS, Gate.PHOTOS]


# A check, and the refusal's message when the caller fails it.
Check = tuple[Callable[[Session, Principal], bool], str]


def _opens(session: Session, caller: Principal) -> bool:
    return may_open_requests(session, caller)


def _person(_: Session, caller: Principal) -> bool:
    return caller.user is not None


def _requester(_: Session, caller: Principal) -> bool:
    return caller.user is not None and caller.user.requester


def _person_or_admin(_: Session, caller: Principal) -> bool:
    return caller.user is not None or is_admin(caller)


def _not_a_scanner(_: Session, caller: Principal) -> bool:
    return caller.device is None


def _editor(_: Session, caller: Principal) -> bool:
    role = caller.role
    return role is not None and role.allows(Role.EDITOR)


def _changes_holds(_: Session, caller: Principal) -> bool:
    return changes_holds(caller)


def _signed_in_admin(_: Session, caller: Principal) -> bool:
    return caller.user is not None and is_admin(caller)


_OPEN: Check = (_opens, NO_ACCESS)
_EDITOR: list[Check] = [(_not_a_scanner, NO_SCANNERS), (_editor, NOT_AN_EDITOR)]

# In order: the first a caller fails is the refusal they get. A signed-in Admin always may
# open the Requests pages, so HOLDS and PHOTOS refuse with their own message first.
CHECKS: dict[Gate, list[Check]] = {
    Gate.OPEN: [_OPEN],
    Gate.SUBMIT: [(_requester, NOT_A_REQUESTER)],
    Gate.EDIT: [_OPEN, (_person, NOT_A_REQUESTER)],
    Gate.MOVE: [_OPEN, (_person_or_admin, NOT_YOURS_TO_MOVE)],
    Gate.PRIORITY: _EDITOR,
    Gate.COUNT: _EDITOR,
    Gate.HOLDS: [(_changes_holds, HOLDS_ADMINS_ONLY), _OPEN],
    Gate.PHOTOS: [(_signed_in_admin, photos.ADMINS_ONLY), _OPEN],
}


def why_not(session: Session, caller: Principal, gate: Gate) -> str | None:
    """Why the caller doesn't pass the gate, or None when they do."""
    for passes, message in CHECKS[gate]:
        if not passes(session, caller):
            return message
    return None
