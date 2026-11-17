"""Sync the catalog from its two sources: the Open Filament Database's (OFDB's) JSON export,
and BambuStudio's color code list on GitHub.

One sync run covers both sources, OFDB first. Each source downloads its file, asking with
If-None-Match and If-Modified-Since whether it changed since the copy in use; a 304 is a
successful attempt, "Not modified". A new file replaces every row of that source in one
transaction. Any failure (network, an incomplete download, bad JSON, missing fields) is
recorded for that source with a short reason and leaves its copy as it was; neither
source's failure stops the other.

Every run ends by working out catalog links again, whatever each source's result: the only
product data a sync writes. Only one run happens at a time: a second one asked for meanwhile
raises SyncBusy instead of starting. A run writes nothing to spools, tags or events.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.catalog_models import (
    ETAG_LENGTH,
    LAST_MODIFIED_LENGTH,
    BambuColorCode,
    CatalogBrand,
    CatalogFilament,
    CatalogSize,
    CatalogSource,
    CatalogSync,
    CatalogVariant,
    SyncResult,
)
from filament_tracker.db.types import utcnow
from filament_tracker.services.bambustudio_codes import ListInvalid, parse_color_codes
from filament_tracker.services.catalog_download import Copy, DownloadFailed, download
from filament_tracker.services.catalog_export import ExportInvalid, parse_export
from filament_tracker.services.catalog_links import update_links

logger = logging.getLogger(__name__)

OFDB_EXPORT_URL = "https://api.openfilamentdatabase.org/json/all.json.gz"
BAMBUSTUDIO_URL = (
    "https://raw.githubusercontent.com/bambulab/BambuStudio/master/resources/profiles/BBL/"
    "filament/filaments_color_codes.json"
)
# The gzipped export is about 3.5 MB today.
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
# The list is about 250 KB today.
MAX_BAMBUSTUDIO_BYTES = 16 * 1024 * 1024


class SyncBusy(Exception):
    """A sync is already running."""


class _StoreFailed(Exception):
    """The new copy could not be stored."""


@dataclass(frozen=True)
class SourceStatus:
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_result: SyncResult | None
    # Why the last attempt failed, when it did.
    last_reason: str | None
    # OFDB's only.
    dataset_version: str | None


@dataclass(frozen=True)
class SyncStatus:
    # Catalog colors in the copy in use.
    colors: int
    ofdb: SourceStatus
    bambustudio: SourceStatus


@dataclass(frozen=True)
class _Parsed:
    """A source's new copy: its version, if any, and how to write its rows."""

    version: str | None
    write: Callable[[Session], None]
    summary: str


def _ofdb(body: bytes) -> _Parsed:
    export = parse_export(body)

    def write(session: Session) -> None:
        for model in (CatalogSize, CatalogVariant, CatalogFilament, CatalogBrand):
            session.execute(delete(model))
        session.execute(insert(CatalogBrand), [export.brand])
        session.execute(insert(CatalogFilament), export.filaments)
        if export.variants:
            session.execute(insert(CatalogVariant), export.variants)
        if export.sizes:
            session.execute(insert(CatalogSize), export.sizes)

    return _Parsed(export.version, write, f"{len(export.variants)} catalog colors")


def _bambustudio(body: bytes) -> _Parsed:
    rows = parse_color_codes(body)

    def write(session: Session) -> None:
        session.execute(delete(BambuColorCode))
        session.execute(insert(BambuColorCode), rows)

    return _Parsed(None, write, f"{len(rows)} Bambu codes")


@dataclass(frozen=True)
class _Source:
    source: CatalogSource
    url: str
    # Names the server in failure reasons.
    server: str
    max_bytes: Callable[[], int]
    parse: Callable[[bytes], _Parsed]


# Limits are read when used, so tests can lower them.
_SOURCES = (
    _Source(CatalogSource.OFDB, OFDB_EXPORT_URL, "OFDB", lambda: MAX_DOWNLOAD_BYTES, _ofdb),
    _Source(
        CatalogSource.BAMBUSTUDIO,
        BAMBUSTUDIO_URL,
        "GitHub",
        lambda: MAX_BAMBUSTUDIO_BYTES,
        _bambustudio,
    ),
)


class CatalogSyncer:
    """Runs catalog syncs and reports their status."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = sessions
        self._transport = transport
        self._clock = clock
        self._running = threading.Lock()

    def sync(self) -> SyncStatus:
        """Sync both sources once and return the new status. Raises SyncBusy if a sync is
        running."""
        if not self._running.acquire(blocking=False):
            raise SyncBusy
        try:
            for source in _SOURCES:
                self._sync(source)
            self._update_links()
        finally:
            self._running.release()
        return self.status()

    def never_synced(self) -> bool:
        """Whether either source has never synced, so its copy is missing."""
        with self._sessions() as session:
            return any(last_success(session, s.source) is None for s in _SOURCES)

    def status(self) -> SyncStatus:
        with self._sessions() as session:
            colors = session.scalar(select(func.count()).select_from(CatalogVariant)) or 0
            return SyncStatus(
                colors=colors,
                ofdb=_status(session, CatalogSource.OFDB),
                bambustudio=_status(session, CatalogSource.BAMBUSTUDIO),
            )

    def _update_links(self) -> None:
        """Work out catalog links again, whatever each source's result."""
        try:
            with self._sessions() as session, session.begin():
                update_links(session)
        except SQLAlchemyError:
            logger.exception("catalog links could not be updated")

    def _sync(self, source: _Source) -> None:
        started = self._clock()
        with self._sessions() as session:
            previous = last_success(session, source.source)
        copy = Copy(previous.etag, previous.last_modified) if previous else None
        try:
            got = download(
                source.url,
                server=source.server,
                copy=copy,
                max_bytes=source.max_bytes(),
                transport=self._transport,
            )
            if previous is not None and got.not_modified:
                self._record(
                    started,
                    source.source,
                    SyncResult.NOT_MODIFIED,
                    version=previous.dataset_version,
                    etag=_fits(got.etag, ETAG_LENGTH) or previous.etag,
                    last_modified=_fits(got.last_modified, LAST_MODIFIED_LENGTH)
                    or previous.last_modified,
                )
                return
            parsed = source.parse(got.body)
            self._replace(started, source.source, parsed, got.etag, got.last_modified)
        except (DownloadFailed, ExportInvalid, ListInvalid, _StoreFailed) as error:
            logger.warning("catalog sync of %s failed: %s", source.source, error)
            self._record(started, source.source, SyncResult.FAILED, reason=str(error))

    def _replace(
        self,
        started: datetime,
        source: CatalogSource,
        parsed: _Parsed,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        """Swap the source's rows and record the sync, in one transaction."""
        try:
            with self._sessions() as session, session.begin():
                parsed.write(session)
                session.add(
                    self._attempt(
                        started,
                        source,
                        SyncResult.UPDATED,
                        version=parsed.version,
                        etag=_fits(etag, ETAG_LENGTH),
                        last_modified=_fits(last_modified, LAST_MODIFIED_LENGTH),
                    )
                )
        except SQLAlchemyError as error:
            raise _StoreFailed(f"could not store the {source} copy") from error
        logger.info("catalog %s updated: %s", source, parsed.summary)

    def _record(
        self, started: datetime, source: CatalogSource, result: SyncResult, **fields: str | None
    ) -> None:
        with self._sessions() as session, session.begin():
            session.add(self._attempt(started, source, result, **fields))

    def _attempt(
        self,
        started: datetime,
        source: CatalogSource,
        result: SyncResult,
        *,
        reason: str | None = None,
        version: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> CatalogSync:
        return CatalogSync(
            source=source,
            started_at=started,
            finished_at=self._clock(),
            result=result,
            reason=reason,
            dataset_version=version,
            etag=etag,
            last_modified=last_modified,
        )


def _status(session: Session, source: CatalogSource) -> SourceStatus:
    last = last_attempt(session, source)
    success = last_success(session, source)
    return SourceStatus(
        last_success_at=success.finished_at if success else None,
        last_attempt_at=last.finished_at if last else None,
        last_result=last.result if last else None,
        last_reason=last.reason if last else None,
        dataset_version=success.dataset_version if success else None,
    )


def last_attempt(session: Session, source: CatalogSource) -> CatalogSync | None:
    """The source's latest sync attempt, whatever its result."""
    return session.scalars(
        select(CatalogSync).where(CatalogSync.source == source).order_by(CatalogSync.id.desc())
    ).first()


def last_success(session: Session, source: CatalogSource) -> CatalogSync | None:
    """The source's latest sync that worked (a new copy, or Not modified)."""
    return session.scalars(
        select(CatalogSync)
        .where(CatalogSync.source == source, CatalogSync.result != SyncResult.FAILED)
        .order_by(CatalogSync.id.desc())
    ).first()


def _fits(value: str | None, length: int) -> str | None:
    """A header too long to keep is dropped: the next sync then downloads in full."""
    return value if value is not None and len(value) <= length else None
