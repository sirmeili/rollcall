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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from filament_tracker.api.request_files import content_disposition
from filament_tracker.api.request_schemas import PhotosIn, PhotoUploadOut, RequestOut
from filament_tracker.api.request_views import model_files, request_out
from filament_tracker.api.requests import RequestsCaller, find_request, send_after_commit
from filament_tracker.auth import AnyPrincipal, DbSession, forbidden, problems
from filament_tracker.db.models import User
from filament_tracker.db.request_models import FILE_NAME_MAX, PrintRequest, RequestPhoto
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.print_requests import emails, photos
from filament_tracker.print_requests.rules import Problems

PHOTO_UPLOAD_PATH = "/requests/photo-uploads"

router = APIRouter(tags=["requests"])


def photo_admin(principal: AnyPrincipal) -> User:
    """A signed-in Admin, checked before the body is read. Tokens act for no one, and a photo
    records who uploaded it."""
    role = principal.role
    if principal.user is None or role is None or not role.allows(Role.ADMIN):
        raise forbidden(photos.ADMINS_ONLY)
    return principal.user


PhotoAdmin = Annotated[User, Depends(photo_admin)]


def stored_photos(http: Request) -> photos.Photos:
    return photos.Photos(model_files(http))


def _photo(session: Session, found: PrintRequest, photo_id: UUID) -> RequestPhoto:
    photo = session.get(RequestPhoto, photo_id)
    if photo is None or photo.request_id != found.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such photo")
    return photo


@router.post(PHOTO_UPLOAD_PATH, response_model=PhotoUploadOut, status_code=201)
async def upload_photo(
    http: Request,
    user: PhotoAdmin,
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
    try:
        photo = await run_in_threadpool(photos.reencode, body)
    except photos.NotAPhoto as error:
        raise problems({photos.PHOTO: str(error)}) from None
    stored = stored_photos(http).store(session, user, name, photo, utcnow())
    session.commit()
    return PhotoUploadOut(id=stored.id, name=stored.file_name)


@router.post("/requests/{request_id}/photos", response_model=RequestOut)
def add_photos(
    request_id: int,
    body: PhotosIn,
    _: PhotoAdmin,
    caller: RequestsCaller,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Save photo uploads with a Done or Picked Up request, up to 4 photos in all, emailing
    the requester the new photos."""
    found = find_request(session, caller, request_id)
    try:
        added = photos.add(session, found, body.photo_ids, caller.user, utcnow())
    except Problems as error:
        raise problems(error.problems) from None
    session.commit()
    send_after_commit(
        http,
        lambda public_url: emails.new_photo_emails(
            found, caller.user, stored_photos(http).email_copies(added), public_url
        ),
    )
    session.refresh(found)
    return request_out(http, session, caller, found)


@router.delete("/requests/{request_id}/photos/{photo_id}", response_model=RequestOut)
def remove_photo(
    request_id: int,
    photo_id: UUID,
    _: PhotoAdmin,
    caller: RequestsCaller,
    session: DbSession,
    http: Request,
) -> RequestOut:
    """Remove a photo from a Done or Picked Up request, deleting its files."""
    found = find_request(session, caller, request_id)
    photo = _photo(session, found, photo_id)
    try:
        photos.remove(session, found, photo, caller.user, utcnow())
    except Problems as error:
        raise problems(error.problems) from None
    session.commit()
    stored_photos(http).delete(photo)
    session.refresh(found)
    return request_out(http, session, caller, found)


@router.get("/requests/{request_id}/photos/{photo_id}")
def photo(
    request_id: int, photo_id: UUID, caller: RequestsCaller, session: DbSession, http: Request
) -> FileResponse:
    """A photo of the request's print, for anyone who can see the request."""
    found = find_request(session, caller, request_id)
    shown = _photo(session, found, photo_id)
    files = model_files(http)
    if not files.exists(shown.stored_name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such photo")
    return FileResponse(
        files.path(shown.stored_name),
        media_type=photos.media_type(shown.stored_name),
        headers={
            "Content-Disposition": content_disposition(shown.file_name, "inline"),
            "X-Content-Type-Options": "nosniff",
        },
    )
