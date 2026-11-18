"""Print requests (ADR-0014, ADR-0017).

The Requests pages are for Editors and Admins (every request), Requesters, and anyone who
has made a request (their own). Submitting and editing need Requester; changing priority
needs Editor. Another user's request answers 404, so its existence isn't revealed.
"""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from filament_tracker.api.request_schemas import (
    PriorityIn,
    RequestEdit,
    RequestIn,
    RequestOut,
    RequestRowOut,
    SubmittedCountOut,
)
from filament_tracker.api.request_views import model_files, request_out, row_out
from filament_tracker.auth import AnyPrincipal, DbSession, Editor, Principal, forbidden
from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.db.types import utcnow
from filament_tracker.print_requests import service
from filament_tracker.print_requests.access import may_open_requests, may_see
from filament_tracker.print_requests.choices import ChoiceInput
from filament_tracker.print_requests.read import visible_requests
from filament_tracker.print_requests.rules import Problems, RequestFields

router = APIRouter(prefix="/requests", tags=["requests"])

NO_ACCESS = "requires Requester or the editor role"


def requests_user(principal: AnyPrincipal, session: DbSession) -> Principal:
    """A caller the Requests pages are for."""
    if not may_open_requests(session, principal):
        raise forbidden(NO_ACCESS)
    return principal


RequestsCaller = Annotated[Principal, Depends(requests_user)]


def signed_in_user(principal: Principal) -> User:
    """Only a person submits or edits; tokens act for no one."""
    if principal.user is None:
        raise forbidden(service.NOT_A_REQUESTER)
    return principal.user


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
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"problems": error.problems})
    return forbidden(str(error))


@router.get("", response_model=list[RequestRowOut])
def list_requests(caller: RequestsCaller, session: DbSession) -> list[RequestRowOut]:
    """Every request for Editors and Admins, otherwise the caller's own: most urgent first,
    then by needed-by date (no date last), then oldest first."""
    return [row_out(item) for item in visible_requests(session, caller)]


@router.get("/count", response_model=SubmittedCountOut)
def submitted_count(_: Editor, session: DbSession) -> SubmittedCountOut:
    """The Submitted requests, for the Requests link's count."""
    return SubmittedCountOut(submitted=service.submitted_count(session))


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def submit(body: RequestIn, caller: AnyPrincipal, session: DbSession, http: Request) -> RequestOut:
    user = signed_in_user(caller)
    try:
        created = service.submit(session, user, _fields(body), today=today(http), now=utcnow())
    except (Problems, service.NotAllowed) as error:
        raise _refused(error) from None
    session.commit()
    session.refresh(created)
    return request_out(http, session, caller, created)


@router.get("/{request_id}", response_model=RequestOut)
def read(request_id: int, caller: RequestsCaller, session: DbSession, http: Request) -> RequestOut:
    return request_out(http, session, caller, find_request(session, caller, request_id))


@router.patch("/{request_id}", response_model=RequestOut)
def edit(
    request_id: int, body: RequestEdit, caller: RequestsCaller, session: DbSession, http: Request
) -> RequestOut:
    """The requester edits every field again, while the request is Submitted."""
    found = find_request(session, caller, request_id)
    user = signed_in_user(caller)
    try:
        saved = service.edit(session, found, user, _fields(body), today=today(http), now=utcnow())
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
    service.change_priority(found, caller.user, body.priority, now=utcnow())
    session.commit()
    session.refresh(found)
    return request_out(http, session, caller, found)
