"""Print requests (ADR-0014, ADR-0017).

The Requests pages are for Editors and Admins (every request), Requesters, and anyone who
has made a request (their own). Submitting and editing need Requester; changing priority
needs Editor; moving a request is for the people the pipeline names. Another user's request
answers 404, so its existence isn't revealed.
"""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from filament_tracker.auth import AnyPrincipal, DbSession, Editor, Principal, forbidden, problems
from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest, RequestPhoto
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament, notifications, photos, pipeline, service
from filament_tracker.print_requests.access import is_admin, may_open_requests, may_see, movers
from filament_tracker.print_requests.choices import ChoiceInput
from filament_tracker.print_requests.read import ListFilter, Tab, visible_requests
from filament_tracker.print_requests.rules import Problems, RequestFields

router = APIRouter(prefix="/requests", tags=["requests"])

NO_ACCESS = "requires Requester or the editor role"
NOT_OPEN = "Filter by open statuses only."
NO_PHOTOS = "Photos can be added only when moving a request to Done."


def requests_user(principal: AnyPrincipal, session: DbSession) -> Principal:
    """A caller the Requests pages are for."""
    if not may_open_requests(session, principal):
        raise forbidden(NO_ACCESS)
    return principal


RequestsCaller = Annotated[Principal, Depends(requests_user)]


def _person(principal: Principal) -> User:
    """Only a person submits or edits; tokens act for no one."""
    if principal.user is None:
        raise forbidden(service.NOT_A_REQUESTER)
    return principal.user


def requester(principal: AnyPrincipal) -> User:
    """A signed-in Requester, checked before the body is read."""
    user = _person(principal)
    if not user.requester:
        raise forbidden(service.NOT_A_REQUESTER)
    return user


def requests_person(principal: RequestsCaller) -> Principal:
    """A signed-in user the Requests pages are for (an edit's own rules come after)."""
    _person(principal)
    return principal


def mover(principal: RequestsCaller) -> Principal:
    """A caller who might move a request: an Admin, or a person who might own one. Which
    moves they may make is the pipeline's to say."""
    if principal.user is None and not is_admin(principal):
        raise forbidden(pipeline.NOT_YOURS_TO_MOVE)
    return principal


RequesterUser = Annotated[User, Depends(requester)]
MovingCaller = Annotated[Principal, Depends(mover)]
RequestsPerson = Annotated[Principal, Depends(requests_person)]


def find_request(session: Session, principal: Principal, request_id: int) -> PrintRequest:
    found = session.get(PrintRequest, request_id)
    if found is None or not may_see(principal, found):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such request")
    return found


def today(http: Request) -> date:
    """Today in the server's time zone, which needed-by dates are judged in."""
    zone = ZoneInfo(http.app.state.settings_store.time_zone())
    return datetime.now(zone).date()


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


def _refused(error: Exception) -> HTTPException:
    if isinstance(error, Problems):
        return problems(error.problems)
    return forbidden(str(error))


@router.get("", response_model=list[RequestRowOut])
def list_requests(
    caller: RequestsCaller,
    session: DbSession,
    tab: Tab = Tab.ACTIVE,
    status_: Annotated[list[RequestStatus] | None, Query(alias="status")] = None,
    mine: bool = False,
) -> list[RequestRowOut]:
    """Every request for Editors and Admins, otherwise the caller's own. The Active tab is
    most urgent first, then by needed-by date (no date last), then oldest first; the Closed
    tab is the latest move first. Editors and Admins may keep only some open statuses
    (`status`, repeated) or only their own requests (`mine`)."""
    statuses = status_ or []
    if any(s.closed for s in statuses):
        raise problems({"status": NOT_OPEN})
    wanted = ListFilter(tab=tab, statuses=statuses, mine=mine)
    return [row_out(item) for item in visible_requests(session, caller, wanted)]


@router.get("/count", response_model=SubmittedCountOut)
def submitted_count(_: Editor, session: DbSession) -> SubmittedCountOut:
    """The Submitted requests, for the Requests link's count."""
    return SubmittedCountOut(submitted=service.submitted_count(session))


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def submit(
    body: RequestIn, user: RequesterUser, caller: AnyPrincipal, session: DbSession, http: Request
) -> RequestOut:
    try:
        created = service.submit(session, user, _fields(body), today=today(http), now=utcnow())
    except (Problems, service.NotAllowed) as error:
        raise _refused(error) from None
    session.commit()
    notify_after_commit(http, session, lambda: notifications.new_request(created))
    session.refresh(created)
    return request_out(http, session, caller, created)


@router.get("/{request_id}", response_model=RequestOut)
def read(request_id: int, caller: RequestsCaller, session: DbSession, http: Request) -> RequestOut:
    return request_out(http, session, caller, find_request(session, caller, request_id))


@router.patch("/{request_id}", response_model=RequestOut)
def edit(
    request_id: int, body: RequestEdit, caller: RequestsPerson, session: DbSession, http: Request
) -> RequestOut:
    """The requester edits every field again, while the request is Submitted."""
    found = find_request(session, caller, request_id)
    user = _person(caller)
    try:
        saved = service.edit(
            session,
            found,
            user,
            _fields(body),
            today=today(http),
            now=utcnow(),
            file_on_disk=model_files(http).exists(found.file_stored_name),
        )
    except (Problems, service.NotAllowed) as error:
        raise _refused(error) from None
    session.commit()
    model_files(http).delete(saved.old_file)
    session.refresh(found)
    return request_out(http, session, caller, found)


@router.post("/{request_id}/priority", response_model=RequestOut)
def change_priority(
    request_id: int, body: PriorityIn, caller: Editor, session: DbSession, http: Request
) -> RequestOut:
    found = find_request(session, caller, request_id)
    try:
        service.change_priority(found, caller.user, body.priority, now=utcnow())
    except service.NotAllowed as error:
        raise forbidden(str(error)) from None
    session.commit()
    session.refresh(found)
    return request_out(http, session, caller, found)


@router.post("/{request_id}/moves", response_model=RequestOut)
def make_move(
    request_id: int, body: MoveIn, caller: MovingCaller, session: DbSession, http: Request
) -> RequestOut:
    """Move the request to another status, saving any photo uploads with a move that takes
    them (Done). Approve takes grams for every filament choice, holds them and moves on by
    itself to Queued or Waiting on Filament; Done, Failed and Cancelled release its holds.
    It answers 409 when the request is no longer in `from_status`, and 403 when the pipeline
    has no such move for the caller. Nothing is saved when it is refused."""
    found = find_request(session, caller, request_id)
    now = utcnow()
    added: list[RequestPhoto] = []
    try:
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
                raise Problems({photos.PHOTOS: NO_PHOTOS})
            added = photos.add(session, found, body.photo_ids, caller.user, now)
    except pipeline.Stale as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except pipeline.NotAMove as error:
        raise forbidden(str(error)) from None
    except Problems as error:
        raise problems(error.problems) from None
    session.commit()
    notify_after_commit(
        http,
        session,
        lambda: notifications.request_moved(
            moved, stored_photos(http).email_copies(added), added[0].id if added else None
        ),
    )
    session.refresh(found)
    return request_out(http, session, caller, found)
