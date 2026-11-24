"""Photos of a finished print: up to 4 per request, added by Admins in the Done move or later
while the request is Done or Picked Up, and seen by anyone who can see the request.

A photo is a JPEG or PNG judged by its contents, at most 20 MB and 40 megapixels (a guard
against decompression bombs, checked before the pixels are decoded). Every photo is decoded
and re-encoded with its orientation applied, which drops EXIF, GPS, ICC profiles, text and
any other metadata. The full photo keeps its format; the email copy is a JPEG at most
1024 px on its long side.

Both copies are stored in the request-files directory beside model files, under random
names. As with model files, an upload waits until it is saved with a request, and uploads
never saved are removed after a day.
"""

import io
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest, RequestHistory, RequestPhoto
from filament_tracker.domain.enums import HistoryKind, RequestStatus
from filament_tracker.print_requests.files import UNCLAIMED_FOR, ModelFiles, clean_name
from filament_tracker.print_requests.refused import Refused

MAX_PHOTO_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_PHOTOS = 4
EMAIL_LONG_SIDE = 1024
EMAIL_QUALITY = 85
FULL_QUALITY = 92
# Pillow judges the format by the contents; only these two are ever opened.
FORMATS = {"JPEG": ".jpg", "PNG": ".png"}
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png"}
# While these statuses last, Admins add and remove photos outside the Done move.
PHOTO_STATUSES = frozenset({RequestStatus.DONE, RequestStatus.PICKED_UP})

PHOTO = "photo"
PHOTOS = "photos"

NOT_A_PHOTO = "That isn't a JPEG or PNG photo."
TOO_MANY_PIXELS = "That photo is too large. Use one under 40 megapixels."
TOO_MANY_PHOTOS = f"A request can have up to {MAX_PHOTOS} photos."
PHOTO_GONE = "That photo's upload wasn't found. Upload it again."
NOT_NOW = "Photos can be added or removed only while the request is Done or Picked Up."
ADMINS_ONLY = "Only Admins add or remove photos."


@dataclass(frozen=True)
class Reencoded:
    """A photo decoded and encoded again: the full photo, its extension, and the email copy."""

    full: bytes
    suffix: str
    email: bytes


def _flattened(image: Image.Image) -> Image.Image:
    """RGB for a JPEG, with any transparency laid over white."""
    if image.mode not in ("RGBA", "LA", "P"):
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    white = Image.new("RGB", rgba.size, (255, 255, 255))
    white.paste(rgba, mask=rgba.getchannel("A"))
    return white


def reencode(data: bytes) -> Reencoded:
    """Check and re-encode an uploaded photo; Refused if it isn't one we take."""
    try:
        image = Image.open(io.BytesIO(data), formats=list(FORMATS))
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise Refused.invalid({PHOTO: NOT_A_PHOTO}) from None
    image_format = image.format or ""
    width, height = image.size
    if width * height > MAX_PIXELS:
        raise Refused.invalid({PHOTO: TOO_MANY_PIXELS})
    try:
        image.load()
        turned = ImageOps.exif_transpose(image)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise Refused.invalid({PHOTO: NOT_A_PHOTO}) from None
    # Anything Pillow kept from the file (EXIF, ICC profile, text) is left behind here.
    turned.info = {}

    # A decoded JPEG is L, RGB or CMYK, each of which saves as a JPEG again.
    full = io.BytesIO()
    if image_format == "JPEG":
        turned.save(full, "JPEG", quality=FULL_QUALITY)
    else:
        turned.save(full, "PNG", optimize=True)

    small = _flattened(turned)
    small.thumbnail((EMAIL_LONG_SIDE, EMAIL_LONG_SIDE))
    email = io.BytesIO()
    small.save(email, "JPEG", quality=EMAIL_QUALITY)
    return Reencoded(full.getvalue(), FORMATS[image_format], email.getvalue())


def media_type(stored_name: str) -> str:
    """The full photo's content type, from the extension it was stored with."""
    return MEDIA_TYPES[stored_name[stored_name.rfind(".") :]]


class Photos:
    """Photos in the request-files directory, and the rules for adding and removing them."""

    def __init__(self, files: ModelFiles) -> None:
        self.files = files

    def store(
        self, session: Session, user: User, name: str, photo: Reencoded, now: datetime
    ) -> RequestPhoto:
        """Keep a re-encoded photo, waiting for a request to be saved with it."""
        self.files.directory.mkdir(parents=True, exist_ok=True)
        self._forget_unclaimed(session, now)
        full = secrets.token_hex(16) + photo.suffix
        email = secrets.token_hex(16) + ".jpg"
        self.files.path(full).write_bytes(photo.full)
        self.files.path(email).write_bytes(photo.email)
        stored = RequestPhoto(
            stored_name=full,
            email_stored_name=email,
            uploaded_by=user.id,
            uploaded_at=now,
            file_name=clean_name(name, f"photo{photo.suffix}"),
        )
        session.add(stored)
        return stored

    def email_copies(self, photos: Iterable[RequestPhoto]) -> list[bytes]:
        """The email copies of these photos, leaving out any whose file is gone."""
        names = (photo.email_stored_name for photo in photos)
        return [self.files.path(name).read_bytes() for name in names if self.files.exists(name)]

    def delete(self, photo: RequestPhoto) -> None:
        self.files.delete(photo.stored_name)
        self.files.delete(photo.email_stored_name)

    def _forget_unclaimed(self, session: Session, now: datetime) -> None:
        old = session.scalars(
            select(RequestPhoto).where(
                RequestPhoto.request_id.is_(None), RequestPhoto.uploaded_at < now - UNCLAIMED_FOR
            )
        )
        for photo in old:
            self.delete(photo)
            session.delete(photo)


def add(
    session: Session,
    request: PrintRequest,
    photo_ids: list[UUID],
    user: User | None,
    now: datetime,
) -> list[RequestPhoto]:
    """Save an Admin's waiting uploads with a Done or Picked Up request, writing a
    `photo_added` entry for each. Refused if an upload isn't theirs and waiting, or the
    request would have more than 4 photos."""
    if request.status not in PHOTO_STATUSES:
        raise Refused.invalid({PHOTOS: NOT_NOW})
    found: list[RequestPhoto] = []
    for photo_id in dict.fromkeys(photo_ids):
        photo = session.get(RequestPhoto, photo_id)
        if (
            photo is None
            or photo.request_id is not None
            or user is None
            or photo.uploaded_by != user.id
        ):
            raise Refused.invalid({PHOTOS: PHOTO_GONE})
        found.append(photo)
    if len(request.photos) + len(found) > MAX_PHOTOS:
        raise Refused.invalid({PHOTOS: TOO_MANY_PHOTOS})
    for photo in found:
        request.photos.append(photo)
        request.history.append(
            RequestHistory(kind=HistoryKind.PHOTO_ADDED, user=user, at=now, note=photo.file_name)
        )
    if found:
        request.updated_at = now
    return found


def remove(
    session: Session, request: PrintRequest, photo: RequestPhoto, user: User | None, now: datetime
) -> None:
    """Take a photo off a Done or Picked Up request, writing a `photo_removed` entry. Its
    files are for the caller to delete once this is committed."""
    if request.status not in PHOTO_STATUSES:
        raise Refused.invalid({PHOTOS: NOT_NOW})
    request.photos.remove(photo)
    session.delete(photo)
    request.history.append(
        RequestHistory(kind=HistoryKind.PHOTO_REMOVED, user=user, at=now, note=photo.file_name)
    )
    request.updated_at = now
