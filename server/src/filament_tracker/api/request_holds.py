"""Changing a print request's holds by hand: a filament choice's grams, a hold on a spool, a
hold's spool or grams, or removing a hold.

For signed-in Admins only; tokens are refused, since a change records who made it. Each
change names the status the caller saw the request in, and answers 409 when it has moved on,
403 when the request isn't Approved, Waiting on Filament or Queued, and 404 for a choice or
hold that isn't the request's. Nothing is saved when it is refused, and no email is sent.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from filament_tracker.api.request_schemas import ChoiceGramsIn, HoldIn, RequestOut
from filament_tracker.api.request_views import request_out
from filament_tracker.api.requests import RequestsCaller, find_request
from filament_tracker.auth import AnyPrincipal, DbSession, Principal, forbidden, problems
from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import holds_by_hand, pipeline
from filament_tracker.print_requests.access import changes_holds
from filament_tracker.print_requests.rules import Problems

ADMINS_ONLY = "Only a signed-in Admin changes holds."

router = APIRouter(prefix="/requests", tags=["requests"])


def holds_admin(principal: AnyPrincipal) -> User:
    """A signed-in Admin, checked before the body is read."""
    if not changes_holds(principal) or principal.user is None:
        raise forbidden(ADMINS_ONLY)
    return principal.user


HoldsAdmin = Annotated[User, Depends(holds_admin)]


def _change(
    http: Request,
    session: Session,
    caller: Principal,
    found: PrintRequest,
    change: Callable[[], None],
) -> RequestOut:
    """Make the change and commit it, or refuse it with nothing saved; the request after."""
    try:
        change()
    except pipeline.Stale as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except pipeline.NotAMove as error:
        raise forbidden(str(error)) from None
    except holds_by_hand.NotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from None
    except Problems as error:
        raise problems(error.problems) from None
    session.commit()
    session.refresh(found)
    return request_out(http, session, caller, found)


@router.put("/{request_id}/choices/{choice_id}/grams", response_model=RequestOut)
def set_grams(
    request_id: int,
    choice_id: int,
    body: ChoiceGramsIn,
    user: HoldsAdmin,
    caller: RequestsCaller,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Give a filament choice new grams, releasing its holds and holding them again."""
    found = find_request(session, caller, request_id)
    return _change(
        http,
        session,
        caller,
        found,
        lambda: holds_by_hand.set_grams(
            session,
            found,
            holds_by_hand.choice_of(found, choice_id),
            expected=body.from_status,
            grams=body.grams,
            user=user,
            now=utcnow(),
        ),
    )


@router.post("/{request_id}/choices/{choice_id}/holds", response_model=RequestOut)
def add_hold(
    request_id: int,
    choice_id: int,
    body: HoldIn,
    user: HoldsAdmin,
    caller: RequestsCaller,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Hold grams of a Sealed or Open spool, of any product, for a filament choice: no more
    than the spool has available."""
    found = find_request(session, caller, request_id)
    return _change(
        http,
        session,
        caller,
        found,
        lambda: holds_by_hand.add_hold(
            session,
            found,
            holds_by_hand.choice_of(found, choice_id),
            expected=body.from_status,
            spool_id=body.spool_id,
            grams=body.grams,
            user=user,
            now=utcnow(),
        ),
    )


@router.put("/{request_id}/holds/{hold_id}", response_model=RequestOut)
def change_hold(
    request_id: int,
    hold_id: int,
    body: HoldIn,
    user: HoldsAdmin,
    caller: RequestsCaller,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Replace a hold with grams of a spool, the same one or another, releasing it."""
    found = find_request(session, caller, request_id)
    return _change(
        http,
        session,
        caller,
        found,
        lambda: holds_by_hand.change_hold(
            session,
            found,
            hold_id,
            expected=body.from_status,
            spool_id=body.spool_id,
            grams=body.grams,
            user=user,
            now=utcnow(),
        ),
    )


@router.delete("/{request_id}/holds/{hold_id}", response_model=RequestOut)
def remove_hold(
    request_id: int,
    hold_id: int,
    from_status: RequestStatus,
    user: HoldsAdmin,
    caller: RequestsCaller,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Release a hold. `from_status` names the status the caller saw the request in."""
    found = find_request(session, caller, request_id)
    return _change(
        http,
        session,
        caller,
        found,
        lambda: holds_by_hand.remove_hold(
            session, found, hold_id, expected=from_status, user=user, now=utcnow()
        ),
    )
