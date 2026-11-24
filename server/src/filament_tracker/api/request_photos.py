"""Photos of finished prints: uploading one, saving uploads with a request, removing one, and
serving a photo.

An upload's body is the photo itself, up to 20 MB (this route has its own body limit). It is
checked and re-encoded, then kept until it is saved with a request, in the Done move or
here. Uploading, adding and removing are for signed-in Admins. A photo is served only to
those who can see its request, as `image/jpeg` or `image/png` with `nosniff`, so a browser
never treats it as anything else.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from filament_tracker.api.request_files import content_disposition
from filament_tracker.api.request_schemas import PhotosIn, PhotoUploadOut, RequestOut
from filament_tracker.api.request_views import request_out, stored_photos
from filament_tracker.api.requests import PhotosCaller, Requests, RequestsCaller
from filament_tracker.auth import DbSession
from filament_tracker.db.models import User
from filament_tracker.db.request_models import FILE_NAME_MAX
from filament_tracker.db.types import utcnow
from filament_tracker.print_requests import photos

PHOTO_UPLOAD_PATH = "/requests/photo-uploads"

router = APIRouter(tags=["requests"])


@router.post(PHOTO_UPLOAD_PATH, response_model=PhotoUploadOut, status_code=201)
async def upload_photo(
    http: Request,
    caller: PhotosCaller,
    session: DbSession,
    name: Annotated[str, Query(max_length=FILE_NAME_MAX)] = "",
) -> PhotoUploadOut:
    """Upload a JPEG or PNG photo of a finished print; the body is the photo. Save it with a
    request by sending its `id` in `photo_ids`, in the Done move or to the request's photos."""
    try:
        body = await http.body()
    except ClientDisconnect:
        # Too large, or the browser went away: nothing was kept, and no one is listening.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "upload not finished") from None
    photo = await run_in_threadpool(photos.reencode, body)
    return await run_in_threadpool(_keep, stored_photos(http), session, caller.user, name, photo)


def _keep(
    kept: photos.Photos, session: Session, user: User, name: str, photo: photos.Reencoded
) -> PhotoUploadOut:
    """Store the photo and commit: file and database work, run off the event loop."""
    stored = kept.store(session, user, name, photo, utcnow())
    session.commit()
    return PhotoUploadOut(id=stored.id, name=stored.file_name)


@router.post("/requests/{request_id}/photos", response_model=RequestOut)
def add_photos(
    request_id: int, body: PhotosIn, caller: PhotosCaller, requests: Requests
) -> RequestOut:
    """Save photo uploads with a Done or Picked Up request, up to 4 photos in all, emailing
    the requester the new photos."""
    return request_out(requests.add_photos(caller, request_id, body.photo_ids))


@router.delete("/requests/{request_id}/photos/{photo_id}", response_model=RequestOut)
def remove_photo(
    request_id: int, photo_id: UUID, caller: PhotosCaller, requests: Requests
) -> RequestOut:
    """Remove a photo from a Done or Picked Up request, deleting its files."""
    return request_out(requests.remove_photo(caller, request_id, photo_id))


@router.get("/requests/{request_id}/photos/{photo_id}")
def photo(
    request_id: int, photo_id: UUID, caller: RequestsCaller, requests: Requests
) -> FileResponse:
    """A photo of the request's print, for anyone who can see the request."""
    shown = requests.photo_file(caller, request_id, photo_id)
    return FileResponse(
        shown.path,
        media_type=shown.media_type,
        headers={
            "Content-Disposition": content_disposition(shown.file_name, "inline"),
            "X-Content-Type-Options": "nosniff",
        },
    )
