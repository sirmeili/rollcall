"""Uploading photos of a finished print, adding them to a request and removing them, and
serving one.

Uploading, adding and removing are for signed-in Admins. Each change is one transaction
(ADR-0023): adding tells the requester about the new photos, and removing deletes the photo's
files, once the change has committed.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import PrintRequest, RequestPhoto
from filament_tracker.print_requests import notifications, photos
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.views import RequestDetail

NO_SUCH_PHOTO = "no such photo"


@dataclass(frozen=True)
class StoredPhoto:
    """A request's photo on disk, its content type, and the name it was uploaded with."""

    path: Path
    media_type: str
    file_name: str


@dataclass(frozen=True)
class PhotoUpload:
    """A photo kept until a request is saved with it, by sending its id."""

    id: UUID
    name: str


class ChangingPhotos(Core):
    def upload_photo(self, caller: Principal, name: str, body: bytes) -> PhotoUpload:
        """Check and re-encode an Admin's JPEG or PNG, keep it and commit; INVALID when it
        isn't a photo. File and image work: call it off the event loop."""
        user = self.check(caller, Gate.PHOTOS)
        photo = photos.reencode(body)
        kept = self._parts.photos.store(self._session, user, name, photo, self._parts.clock.now())
        self._session.commit()
        return PhotoUpload(id=kept.id, name=kept.file_name)

    def add_photos(
        self, caller: Principal, request_id: int, photo_ids: list[UUID]
    ) -> RequestDetail:
        """Save photo uploads with a Done or Picked Up request, up to 4 in all, telling the
        requester about the new photos."""
        user = self.check(caller, Gate.PHOTOS)
        found = self._find(caller, request_id)
        added = photos.add(self._session, found, photo_ids, user, self._parts.clock.now())
        copies = self._parts.photos.email_copies
        return self._saved(
            caller,
            found,
            self._notify(lambda: notifications.new_photos(found, user, *copies(added))),
        )

    def remove_photo(self, caller: Principal, request_id: int, photo_id: UUID) -> RequestDetail:
        """Take a photo off a Done or Picked Up request; its files are deleted once that has
        committed."""
        user = self.check(caller, Gate.PHOTOS)
        found = self._find(caller, request_id)
        photo = self._photo(found, photo_id)
        photos.remove(self._session, found, photo, user, self._parts.clock.now())
        return self._saved(caller, found, lambda: self._parts.photos.delete(photo))

    def photo_file(self, caller: Principal, request_id: int, photo_id: UUID) -> StoredPhoto:
        """A photo of the request, for anyone who can see the request; NOT_FOUND when its
        file is gone."""
        self.check(caller, Gate.OPEN)
        photo = self._photo(self._find(caller, request_id), photo_id)
        path = self._parts.photos.full(photo)
        if path is None:
            raise Refused.not_found(NO_SUCH_PHOTO)
        return StoredPhoto(
            path=path, media_type=photos.media_type(photo.stored_name), file_name=photo.file_name
        )

    def _photo(self, request: PrintRequest, photo_id: UUID) -> RequestPhoto:
        photo = self._session.get(RequestPhoto, photo_id)
        if photo is None or photo.request_id != request.id:
            raise Refused.not_found(NO_SUCH_PHOTO)
        return photo
