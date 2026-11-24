"""Moving a request along the pipeline, and uploading, adding and removing photos of its
print.

Each action is one transaction (ADR-0023): it checks, changes and commits, then hands the
notifications to the notifier and deletes a removed photo's files, and answers the request
as the caller sees it after the commit, with any move the retry made before it.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import PrintRequest, RequestPhoto
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament, notifications, photos
from filament_tracker.print_requests.access import movers
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.views import RequestDetail

NO_PHOTOS = "Photos can be added only when moving a request to Done."
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


class Moving(Core):
    def upload_photo(self, caller: Principal, name: str, body: bytes) -> PhotoUpload:
        """Check and re-encode an Admin's JPEG or PNG, keep it and commit; INVALID when it
        isn't a photo. File and image work: call it off the event loop."""
        user = self.check(caller, Gate.PHOTOS)
        photo = photos.reencode(body)
        kept = self._parts.photos.store(self._session, user, name, photo, self._parts.clock.now())
        self._session.commit()
        return PhotoUpload(id=kept.id, name=kept.file_name)

    def move(
        self,
        caller: Principal,
        request_id: int,
        from_status: RequestStatus,
        to_status: RequestStatus,
        grams: dict[int, int] | None = None,
        note: str = "",
        photo_ids: list[UUID] | None = None,
    ) -> RequestDetail:
        """Move the request from the status the caller saw it in, saving any photo uploads
        with a move that takes them (Done). STALE when it has moved on, FORBIDDEN when the
        pipeline has no such move for the caller."""
        user = self.check(caller, Gate.MOVE)
        found = self._find(caller, request_id)
        now = self._parts.clock.now()
        moved = filament.make_move(
            self._session,
            found,
            expected=from_status,
            to_status=to_status,
            grams=grams or {},
            movers=movers(caller, found),
            user=user,
            note=note,
            now=now,
        )
        added: list[RequestPhoto] = []
        if photo_ids:
            if not moved.move.photos:
                raise Refused.invalid({photos.PHOTOS: NO_PHOTOS})
            added = photos.add(self._session, found, photo_ids, user, now)
        return self._saved(
            caller,
            found,
            self._notify(lambda: notifications.request_moved(moved, *self._copies(added))),
        )

    def add_photos(
        self, caller: Principal, request_id: int, photo_ids: list[UUID]
    ) -> RequestDetail:
        """Save photo uploads with a Done or Picked Up request, up to 4 in all, telling the
        requester about the new photos."""
        user = self.check(caller, Gate.PHOTOS)
        found = self._find(caller, request_id)
        added = photos.add(self._session, found, photo_ids, user, self._parts.clock.now())
        return self._saved(
            caller,
            found,
            self._notify(lambda: notifications.new_photos(found, user, *self._copies(added))),
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
        files = self._parts.model_files
        if not files.exists(photo.stored_name):
            raise Refused.not_found(NO_SUCH_PHOTO)
        return StoredPhoto(
            path=files.path(photo.stored_name),
            media_type=photos.media_type(photo.stored_name),
            file_name=photo.file_name,
        )

    def _photo(self, request: PrintRequest, photo_id: UUID) -> RequestPhoto:
        photo = self._session.get(RequestPhoto, photo_id)
        if photo is None or photo.request_id != request.id:
            raise Refused.not_found(NO_SUCH_PHOTO)
        return photo

    def _copies(self, added: list[RequestPhoto]) -> tuple[list[bytes], UUID | None]:
        """The email copies of the added photos, and the first one's id."""
        return self._parts.photos.email_copies(added), added[0].id if added else None
