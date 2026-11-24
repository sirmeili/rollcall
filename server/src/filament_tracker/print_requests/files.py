"""Model files: one 3MF or STL per print request, kept on the data volume.

Files live in the request-files directory beside the database, under random names, and are
not in the nightly backups (those copy the database only). A file is checked by its
contents, never its extension:

- a 3MF is a zip archive with a `3D/3dmodel.model` entry (only the zip's directory is read)
- an STL is a binary STL whose size matches the triangle count in its header, or an ASCII
  STL starting with `solid`

An upload is checked and kept as waiting until a request is saved with it. Uploads never
saved are removed after a day.
"""

import hashlib
import re
import secrets
import struct
import unicodedata
import zipfile
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.request_models import FILE_NAME_MAX, RequestUpload
from filament_tracker.domain.enums import ModelFileKind
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.rules import FILE

# Under Cloudflare's 100 MB request cap. The upload route's body limit enforces it.
MAX_MODEL_BYTES = 95 * 1024 * 1024
DIRECTORY = "request-files"
THREE_MF_MODEL = "3d/3dmodel.model"
STL_HEADER = 80
STL_TRIANGLE = 50
# Uploads never saved with a request are removed after this long.
UNCLAIMED_FOR = timedelta(days=1)
PARTIAL = ".part"


NOT_A_MODEL = "That isn't a 3MF or STL file. Upload a .3mf or .stl model."


def files_dir(database_url: str) -> Path:
    """The request-files directory beside a SQLite database file (in the working directory's
    data folder for an in-memory one)."""
    url = make_url(database_url)
    if url.database in (None, "", ":memory:"):
        return Path("data") / DIRECTORY
    return Path(url.database).parent / DIRECTORY


_UNSAFE = re.compile(r"[^\w .()+,=@-]")


def clean_name(name: str, fallback: str) -> str:
    """The uploader's file name without path parts or unsafe characters; `fallback` when
    nothing is left."""
    base = re.split(r"[\\/]", name)[-1]
    base = unicodedata.normalize("NFC", base)
    base = _UNSAFE.sub("_", "".join(ch for ch in base if ch.isprintable()))
    base = base.strip(" .")[:FILE_NAME_MAX]
    return base or fallback


def kind_of(path: Path, size: int) -> ModelFileKind:
    """What the file is, from its contents; Refused if neither."""
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as archive:
                names = {n.lower() for n in archive.namelist()}
        except zipfile.BadZipFile:
            raise Refused.invalid({FILE: NOT_A_MODEL}) from None
        if THREE_MF_MODEL in names:
            return ModelFileKind.THREE_MF
        raise Refused.invalid({FILE: NOT_A_MODEL})
    with path.open("rb") as file:
        head = file.read(STL_HEADER + 4)
    if size >= STL_HEADER + 4:
        (triangles,) = struct.unpack_from("<I", head, STL_HEADER)
        if size == STL_HEADER + 4 + triangles * STL_TRIANGLE:
            return ModelFileKind.STL
    if head.lstrip().lower().startswith(b"solid"):
        return ModelFileKind.STL
    raise Refused.invalid({FILE: NOT_A_MODEL})


class ModelFiles:
    """The request-files directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path(self, stored_name: str) -> Path:
        return self.directory / stored_name

    def exists(self, stored_name: str | None) -> bool:
        return stored_name is not None and self.path(stored_name).is_file()

    def delete(self, stored_name: str | None) -> None:
        if stored_name is not None:
            self.path(stored_name).unlink(missing_ok=True)

    async def receive(
        self, session: Session, user: User, name: str, body: AsyncIterator[bytes], now: datetime
    ) -> RequestUpload:
        """Store and check an uploaded file, as waiting for a request to be saved with it."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self._forget_unclaimed(session, now)
        stored = secrets.token_hex(16)
        partial = self.path(stored + PARTIAL)
        digest = hashlib.sha256()
        size = 0
        try:
            with partial.open("wb") as out:
                async for chunk in body:
                    size += len(chunk)
                    digest.update(chunk)
                    out.write(chunk)
            kind = kind_of(partial, size)
            partial.rename(self.path(stored))
        finally:
            partial.unlink(missing_ok=True)
        upload = RequestUpload(
            user_id=user.id,
            stored_name=stored,
            file_name=clean_name(name, f"model.{kind.value}"),
            size=size,
            sha256=digest.hexdigest(),
            kind=kind,
            created_at=now,
        )
        session.add(upload)
        return upload

    def _forget_unclaimed(self, session: Session, now: datetime) -> None:
        old = session.scalars(
            select(RequestUpload).where(RequestUpload.created_at < now - UNCLAIMED_FOR)
        )
        for upload in old:
            self.delete(upload.stored_name)
            session.delete(upload)
