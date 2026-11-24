"""Print requests (ADR-0014, ADR-0017).

The Requests pages are for Editors and Admins (every request), Requesters, and anyone who
has made a request (their own). Submitting and editing need Requester; changing priority
needs Editor; moving a request is for the people the pipeline names. Another user's request
answers 404, so its existence isn't revealed.

A Print Requests refusal answers, from every request route, with its kind's status code
(`refused`): its message, or for INVALID each field's problem under `problems`.
"""

from collections.abc import Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from filament_tracker.api.deps import notify_after_commit
from filament_tracker.api.request_schemas import (
    MoveIn,
    PriorityIn,
    RequestEdit,
    RequestIn,
    RequestOut,
    RequestRowOut,
    SubmittedCountOut,
)
from filament_tracker.api.request_views import model_files, request_out, row_out, stored_photos
from filament_tracker.auth import AnyPrincipal, DbSession, Principal
from filament_tracker.db.request_models import PrintRequest, RequestPhoto
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament, notifications, photos, service
from filament_tracker.print_requests.access import may_see, movers
from filament_tracker.print_requests.choices import ChoiceInput
from filament_tracker.print_requests.interface import Gate, Kind, PrintRequests, Refused, Tab
from filament_tracker.print_requests.rules import RequestFields

router = APIRouter(prefix="/requests", tags=["requests"])

NO_PHOTOS = "Photos can be added only when moving a request to Done."

STATUS = {
    Kind.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    Kind.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    Kind.STALE: status.HTTP_409_CONFLICT,
    Kind.INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


async def refused(request: Request, exc: Exception) -> JSONResponse:
    """The app's handler for a Print Requests refusal."""
    assert isinstance(exc, Refused)  # noqa: S101 - registered for this type
    detail = {"problems": exc.problems} if exc.kind is Kind.INVALID else exc.message
    return JSONResponse(status_code=STATUS[exc.kind], content={"detail": detail})


def print_requests(http: Request, session: DbSession) -> PrintRequests:
    """Print Requests for this HTTP request, bound to its session."""
    return PrintRequests(session, http.app.state.print_requests)


Requests = Annotated[PrintRequests, Depends(print_requests)]


def allowed(gate: Gate) -> Callable[..., Principal]:
    """A dependency that refuses a caller Print Requests doesn't let through the gate, before
    the body is read."""

    def dependency(caller: AnyPrincipal, requests: Requests) -> Principal:
        requests.check(caller, gate)
        return caller

    return dependency


RequestsCaller = Annotated[Principal, Depends(allowed(Gate.OPEN))]
SubmittingCaller = Annotated[Principal, Depends(allowed(Gate.SUBMIT))]
EditingCaller = Annotated[Principal, Depends(allowed(Gate.EDIT))]
MovingCaller = Annotated[Principal, Depends(allowed(Gate.MOVE))]
PriorityCaller = Annotated[Principal, Depends(allowed(Gate.PRIORITY))]
CountingCaller = Annotated[Principal, Depends(allowed(Gate.COUNT))]
HoldsCaller = Annotated[Principal, Depends(allowed(Gate.HOLDS))]
PhotosCaller = Annotated[Principal, Depends(allowed(Gate.PHOTOS))]


def find_request(session: Session, principal: Principal, request_id: int) -> PrintRequest:
    found = session.get(PrintRequest, request_id)
    if found is None or not may_see(principal, found):
        raise Refused.not_found("no such request")
    return found


def _today(http: Request) -> date:
    return http.app.state.print_requests.clock.today()


def _fields(body: RequestIn) -> RequestFields:
    return RequestFields(
        title=body.title,
        notes=body.notes,
        quantity=body.quantity,
        needed_by=body.needed_by,
        priority=body.priority,
        link=body.link,
        choices=[ChoiceInput(c.product_id, c.catalog_color, c.note) for c in body.choices],
        upload_id=body.upload_id,
        remove_file=isinstance(body, RequestEdit) and body.remove_file,
    )


@router.get("", response_model=list[RequestRowOut])
def list_requests(
    caller: RequestsCaller,
    requests: Requests,
    tab: Tab = Tab.ACTIVE,
    status_: Annotated[list[RequestStatus] | None, Query(alias="status")] = None,
    mine: bool = False,
) -> list[RequestRowOut]:
    """Every request for Editors and Admins, otherwise the caller's own. The Active tab is
    most urgent first, then by needed-by date (no date last), then oldest first; the Closed
    tab is the latest move first. Editors and Admins may keep only some open statuses
    (`status`, repeated) or only their own requests (`mine`)."""
    return [row_out(row) for row in requests.list(caller, tab, status_ or [], mine)]


@router.get("/count", response_model=SubmittedCountOut)
def submitted_count(caller: CountingCaller, requests: Requests) -> SubmittedCountOut:
    """The Submitted requests, for the Requests link's count."""
    return SubmittedCountOut(submitted=requests.submitted_count(caller))


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def submit(
    body: RequestIn,
    caller: SubmittingCaller,
    requests: Requests,
    session: DbSession,
    http: Request,
) -> RequestOut:
    created = service.submit(session, caller.user, _fields(body), today=_today(http), now=utcnow())
    session.commit()
    notify_after_commit(http, session, lambda: notifications.new_request(created))
    session.refresh(created)
    return request_out(requests.detail(caller, created.id))


@router.get("/{request_id}", response_model=RequestOut)
def read(request_id: int, caller: RequestsCaller, requests: Requests) -> RequestOut:
    return request_out(requests.detail(caller, request_id))


@router.patch("/{request_id}", response_model=RequestOut)
def edit(
    request_id: int,
    body: RequestEdit,
    caller: EditingCaller,
    requests: Requests,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """The requester edits every field again, while the request is Submitted."""
    found = find_request(session, caller, request_id)
    saved = service.edit(
        session,
        found,
        caller.user,
        _fields(body),
        today=_today(http),
        now=utcnow(),
        file_on_disk=model_files(http).exists(found.file_stored_name),
    )
    session.commit()
    model_files(http).delete(saved.old_file)
    session.refresh(found)
    return request_out(requests.detail(caller, found.id))


@router.post("/{request_id}/priority", response_model=RequestOut)
def change_priority(
    request_id: int,
    body: PriorityIn,
    caller: PriorityCaller,
    requests: Requests,
    session: DbSession,
) -> RequestOut:
    found = find_request(session, caller, request_id)
    service.change_priority(found, caller.user, body.priority, now=utcnow())
    session.commit()
    session.refresh(found)
    return request_out(requests.detail(caller, found.id))


@router.post("/{request_id}/moves", response_model=RequestOut)
def make_move(
    request_id: int,
    body: MoveIn,
    caller: MovingCaller,
    requests: Requests,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Move the request to another status, saving any photo uploads with a move that takes
    them (Done). Approve takes grams for every filament choice, holds them and moves on by
    itself to Queued or Waiting on Filament; Done, Failed and Cancelled release its holds.
    It answers 409 when the request is no longer in `from_status`, and 403 when the pipeline
    has no such move for the caller. Nothing is saved when it is refused."""
    found = find_request(session, caller, request_id)
    now = utcnow()
    added: list[RequestPhoto] = []
    moved = filament.make_move(
        session,
        found,
        expected=body.from_status,
        to_status=body.to_status,
        grams=body.grams,
        movers=movers(caller, found),
        user=caller.user,
        note=body.note,
        now=now,
    )
    if body.photo_ids:
        if not moved.move.photos:
            raise Refused.invalid({photos.PHOTOS: NO_PHOTOS})
        added = photos.add(session, found, body.photo_ids, caller.user, now)
    session.commit()
    notify_after_commit(
        http,
        session,
        lambda: notifications.request_moved(
            moved, stored_photos(http).email_copies(added), added[0].id if added else None
        ),
    )
    session.refresh(found)
    return request_out(requests.detail(caller, found.id))
