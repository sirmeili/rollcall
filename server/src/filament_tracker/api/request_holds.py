"""Changing a print request's holds by hand: a filament choice's grams, a hold on a spool, a
hold's spool or grams, or removing a hold.

For signed-in Admins only; tokens are refused, since a change records who made it. Each
change names the status the caller saw the request in, and answers 409 when it has moved on,
403 when the request isn't Approved, Waiting on Filament or Queued, and then 404 for a choice or
hold that isn't the request's. Nothing is saved when it is refused, and no email is sent.
"""

from collections.abc import Callable

from fastapi import APIRouter
from sqlalchemy.orm import Session

from filament_tracker.api.request_schemas import ChoiceGramsIn, HoldIn, RequestOut
from filament_tracker.api.request_views import request_out
from filament_tracker.api.requests import HoldsCaller, Requests, find_request
from filament_tracker.auth import DbSession, Principal
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament

router = APIRouter(prefix="/requests", tags=["requests"])


def _change(
    requests: Requests,
    session: Session,
    caller: Principal,
    found: PrintRequest,
    change: Callable[[], None],
) -> RequestOut:
    """Make the change and commit it, or refuse it with nothing saved; the request after."""
    change()
    session.commit()
    session.refresh(found)
    return request_out(requests.detail(caller, found.id))


@router.put("/{request_id}/choices/{choice_id}/grams", response_model=RequestOut)
def set_grams(
    request_id: int,
    choice_id: int,
    body: ChoiceGramsIn,
    caller: HoldsCaller,
    requests: Requests,
    session: DbSession,
) -> RequestOut:
    """Give a filament choice new grams, releasing its holds and holding them again."""
    found = find_request(session, caller, request_id)
    return _change(
        requests,
        session,
        caller,
        found,
        lambda: filament.set_grams(
            session,
            found,
            choice_id,
            expected=body.from_status,
            grams=body.grams,
            user=caller.user,
            now=utcnow(),
        ),
    )


@router.post("/{request_id}/choices/{choice_id}/holds", response_model=RequestOut)
def add_hold(
    request_id: int,
    choice_id: int,
    body: HoldIn,
    caller: HoldsCaller,
    requests: Requests,
    session: DbSession,
) -> RequestOut:
    """Hold grams of a Sealed or Open spool, of any product, for a filament choice: no more
    than the spool has available."""
    found = find_request(session, caller, request_id)
    return _change(
        requests,
        session,
        caller,
        found,
        lambda: filament.add_hold(
            session,
            found,
            choice_id,
            expected=body.from_status,
            spool_id=body.spool_id,
            grams=body.grams,
            user=caller.user,
            now=utcnow(),
        ),
    )


@router.put("/{request_id}/holds/{hold_id}", response_model=RequestOut)
def change_hold(
    request_id: int,
    hold_id: int,
    body: HoldIn,
    caller: HoldsCaller,
    requests: Requests,
    session: DbSession,
) -> RequestOut:
    """Replace a hold with grams of a spool, the same one or another, releasing it."""
    found = find_request(session, caller, request_id)
    return _change(
        requests,
        session,
        caller,
        found,
        lambda: filament.change_hold(
            session,
            found,
            hold_id,
            expected=body.from_status,
            spool_id=body.spool_id,
            grams=body.grams,
            user=caller.user,
            now=utcnow(),
        ),
    )


@router.delete("/{request_id}/holds/{hold_id}", response_model=RequestOut)
def remove_hold(
    request_id: int,
    hold_id: int,
    from_status: RequestStatus,
    caller: HoldsCaller,
    requests: Requests,
    session: DbSession,
) -> RequestOut:
    """Release a hold. `from_status` names the status the caller saw the request in."""
    found = find_request(session, caller, request_id)
    return _change(
        requests,
        session,
        caller,
        found,
        lambda: filament.remove_hold(
            session, found, hold_id, expected=from_status, user=caller.user, now=utcnow()
        ),
    )
