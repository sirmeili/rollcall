"""Changing a print request's holds by hand: a filament choice's grams, a hold on a spool, a
hold's spool or grams, or removing a hold.

For signed-in Admins only; tokens are refused, since a change records who made it. Each
change names the status the caller saw the request in, and answers 409 when it has moved on,
403 when the request isn't Approved, Waiting on Filament or Queued, and then 404 for a choice or
hold that isn't the request's. Nothing is saved when it is refused, and no email is sent.
"""

from fastapi import APIRouter

from filament_tracker.api.request_schemas import ChoiceGramsIn, HoldIn, RequestOut
from filament_tracker.api.request_views import request_out
from filament_tracker.api.requests import HoldsCaller, Requests
from filament_tracker.domain.enums import RequestStatus

router = APIRouter(prefix="/requests", tags=["requests"])


@router.put("/{request_id}/choices/{choice_id}/grams", response_model=RequestOut)
def set_grams(
    request_id: int, choice_id: int, body: ChoiceGramsIn, caller: HoldsCaller, requests: Requests
) -> RequestOut:
    """Give a filament choice new grams, releasing its holds and holding them again."""
    return request_out(
        requests.set_grams(caller, request_id, choice_id, seen=body.from_status, grams=body.grams)
    )


@router.post("/{request_id}/choices/{choice_id}/holds", response_model=RequestOut)
def add_hold(
    request_id: int, choice_id: int, body: HoldIn, caller: HoldsCaller, requests: Requests
) -> RequestOut:
    """Hold grams of a Sealed or Open spool, of any product, for a filament choice: no more
    than the spool has available."""
    return request_out(
        requests.add_hold(
            caller,
            request_id,
            choice_id,
            seen=body.from_status,
            spool_id=body.spool_id,
            grams=body.grams,
        )
    )


@router.put("/{request_id}/holds/{hold_id}", response_model=RequestOut)
def change_hold(
    request_id: int, hold_id: int, body: HoldIn, caller: HoldsCaller, requests: Requests
) -> RequestOut:
    """Replace a hold with grams of a spool, the same one or another, releasing it."""
    return request_out(
        requests.change_hold(
            caller,
            request_id,
            hold_id,
            seen=body.from_status,
            spool_id=body.spool_id,
            grams=body.grams,
        )
    )


@router.delete("/{request_id}/holds/{hold_id}", response_model=RequestOut)
def remove_hold(
    request_id: int,
    hold_id: int,
    from_status: RequestStatus,
    caller: HoldsCaller,
    requests: Requests,
) -> RequestOut:
    """Release a hold. `from_status` names the status the caller saw the request in."""
    return request_out(requests.remove_hold(caller, request_id, hold_id, seen=from_status))
