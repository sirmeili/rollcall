"""Model files of print requests: uploading one, and downloading a request's file.

An upload's body is the file itself, up to 95 MB (the only route with more than the app's
small body limit). It is checked by its contents and kept until a request is saved with it.
A download is always an attachment of type application/octet-stream, so a browser never
runs or shows what was uploaded.
"""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from starlette.requests import ClientDisconnect

from filament_tracker.api.request_schemas import UploadOut
from filament_tracker.api.request_views import model_files
from filament_tracker.api.requests import RequesterUser, RequestsCaller, find_request
from filament_tracker.auth import DbSession, problems
from filament_tracker.db.request_models import FILE_NAME_MAX
from filament_tracker.db.types import utcnow
from filament_tracker.print_requests.files import NotAModel
from filament_tracker.print_requests.rules import FILE

UPLOAD_PATH = "/requests/uploads"

router = APIRouter(tags=["requests"])


def content_disposition(name: str, disposition: str = "attachment") -> str:
    """An attachment (or inline content) named `name`, with an ASCII fallback for older
    clients."""
    fallback = "".join(ch if ch.isascii() and ch not in '"\\' else "_" for ch in name)
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


@router.post(UPLOAD_PATH, response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload(
    http: Request,
    user: RequesterUser,
    session: DbSession,
    name: Annotated[str, Query(max_length=FILE_NAME_MAX)] = "",
) -> UploadOut:
    """Upload a 3MF or STL model file; the body is the file. Save it with a request by
    sending its `id` as `upload_id`."""
    try:
        found = await model_files(http).receive(session, user, name, http.stream(), utcnow())
    except NotAModel as error:
        raise problems({FILE: str(error)}) from None
    except ClientDisconnect:
        # Too large, or the browser went away: nothing was kept, and no one is listening.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "upload not finished") from None
    session.commit()
    return UploadOut(id=found.id, name=found.file_name, size=found.size, kind=found.kind)


@router.get("/requests/{request_id}/file")
def download(
    request_id: int, caller: RequestsCaller, session: DbSession, http: Request
) -> FileResponse:
    """The request's model file, for its requester, Editors and Admins."""
    found = find_request(session, caller, request_id)
    files = model_files(http)
    if found.file_stored_name is None or not files.exists(found.file_stored_name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "this request has no file")
    return FileResponse(
        files.path(found.file_stored_name),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": content_disposition(found.file_name or "model"),
            "X-Content-Type-Options": "nosniff",
        },
    )
