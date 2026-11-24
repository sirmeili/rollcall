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
from filament_tracker.api.requests import Requests, RequestsCaller, SubmittingCaller
from filament_tracker.print_requests.interface import FILE_NAME_MAX

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
    caller: SubmittingCaller,
    requests: Requests,
    name: Annotated[str, Query(max_length=FILE_NAME_MAX)] = "",
) -> UploadOut:
    """Upload a 3MF or STL model file; the body is the file. Save it with a request by
    sending its `id` as `upload_id`."""
    try:
        kept = await requests.upload_model(caller, name, http.stream())
    except ClientDisconnect:
        # Too large, or the browser went away: nothing was kept, and no one is listening.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "upload not finished") from None
    return UploadOut(id=kept.id, name=kept.name, size=kept.size, kind=kept.kind)


@router.get("/requests/{request_id}/file")
def download(request_id: int, caller: RequestsCaller, requests: Requests) -> FileResponse:
    """The request's model file, for its requester, Editors and Admins."""
    found = requests.model_file(caller, request_id)
    return FileResponse(
        found.path,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": content_disposition(found.name),
            "X-Content-Type-Options": "nosniff",
        },
    )
