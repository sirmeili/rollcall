"""Sync the catalog from the Open Filament Database (OFDB).

A sync downloads OFDB's JSON export, asking with If-None-Match and If-Modified-Since
whether it changed since the copy in use. A 304 is a successful attempt, "Not modified".
A new export replaces every catalog row in one transaction. Any failure (network, an
incomplete download, bad JSON, missing fields) is recorded with a short reason and leaves
the catalog as it was.

Only one sync runs at a time: a second one asked for meanwhile raises SyncBusy instead of
starting. The catalog never writes to products, spools, tags or events.
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
    CatalogBrand,
    CatalogFilament,
    CatalogSize,
    CatalogSync,
    CatalogVariant,
    SyncResult,
)
from filament_tracker.db.types import utcnow
from filament_tracker.services.catalog_export import CatalogExport, ExportInvalid, parse_export

logger = logging.getLogger(__name__)

OFDB_EXPORT_URL = "https://api.openfilamentdatabase.org/json/all.json.gz"
# The gzipped export is about 3.5 MB today.
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
TIMEOUT = httpx.Timeout(30.0, read=60.0)
USER_AGENT = "RollCall catalog sync"


class SyncBusy(Exception):
    """A sync is already running."""


class _Failed(Exception):
    """The sync failed; the message is the short reason recorded."""


@dataclass(frozen=True)
class SyncStatus:
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_result: SyncResult | None
    # Why the last attempt failed, when it did.
    last_reason: str | None
    dataset_version: str | None
    # Catalog colors in the copy in use.
    colors: int


@dataclass(frozen=True)
class _Download:
    body: bytes
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


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
        """Sync once and return the new status. Raises SyncBusy if a sync is running."""
        if not self._running.acquire(blocking=False):
            raise SyncBusy
        try:
            self._sync()
        finally:
            self._running.release()
        return self.status()

    def status(self) -> SyncStatus:
        with self._sessions() as session:
            last = session.scalars(select(CatalogSync).order_by(CatalogSync.id.desc())).first()
            success = last_success(session)
            colors = session.scalar(select(func.count()).select_from(CatalogVariant)) or 0
        return SyncStatus(
            last_success_at=success.finished_at if success else None,
            last_attempt_at=last.finished_at if last else None,
            last_result=last.result if last else None,
            last_reason=last.reason if last else None,
            dataset_version=success.dataset_version if success else None,
            colors=colors,
        )

    def _sync(self) -> None:
        started = self._clock()
        with self._sessions() as session:
            previous = last_success(session)
        try:
            download = self._download(previous)
            if previous is not None and download.not_modified:
                self._record(
                    started,
                    SyncResult.NOT_MODIFIED,
                    version=previous.dataset_version,
                    etag=_fits(download.etag, ETAG_LENGTH) or previous.etag,
                    last_modified=_fits(download.last_modified, LAST_MODIFIED_LENGTH)
                    or previous.last_modified,
                )
                return
            export = parse_export(download.body)
            self._replace(started, export, download)
        except (_Failed, ExportInvalid) as error:
            logger.warning("catalog sync failed: %s", error)
            self._record(started, SyncResult.FAILED, reason=str(error))

    def _download(self, previous: CatalogSync | None) -> _Download:
        headers = {"User-Agent": USER_AGENT}
        if previous is not None and previous.etag:
            headers["If-None-Match"] = previous.etag
        if previous is not None and previous.last_modified:
            headers["If-Modified-Since"] = previous.last_modified
        try:
            with (
                httpx.Client(
                    transport=self._transport, timeout=TIMEOUT, follow_redirects=True
                ) as client,
                client.stream("GET", OFDB_EXPORT_URL, headers=headers) as response,
            ):
                etag = response.headers.get("ETag")
                last_modified = response.headers.get("Last-Modified")
                if response.status_code == 304 and previous is not None:
                    return _Download(b"", etag, last_modified, not_modified=True)
                if response.status_code != 200:
                    raise _Failed(f"OFDB answered {response.status_code}")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_DOWNLOAD_BYTES:
                        raise _Failed("download too large")
        except httpx.TimeoutException:
            raise _Failed("OFDB did not answer in time") from None
        except (httpx.RemoteProtocolError, httpx.ReadError):
            raise _Failed("download incomplete") from None
        except httpx.HTTPError:
            raise _Failed("could not reach OFDB") from None
        return _Download(bytes(body), etag, last_modified)

    def _replace(self, started: datetime, export: CatalogExport, download: _Download) -> None:
        """Swap the whole catalog and record the sync, in one transaction."""
        try:
            with self._sessions() as session, session.begin():
                for model in (CatalogSize, CatalogVariant, CatalogFilament, CatalogBrand):
                    session.execute(delete(model))
                session.execute(insert(CatalogBrand), [export.brand])
                session.execute(insert(CatalogFilament), export.filaments)
                if export.variants:
                    session.execute(insert(CatalogVariant), export.variants)
                if export.sizes:
                    session.execute(insert(CatalogSize), export.sizes)
                session.add(
                    self._attempt(
                        started,
                        SyncResult.UPDATED,
                        version=export.version,
                        etag=_fits(download.etag, ETAG_LENGTH),
                        last_modified=_fits(download.last_modified, LAST_MODIFIED_LENGTH),
                    )
                )
        except SQLAlchemyError as error:
            raise _Failed("could not store the catalog") from error
        logger.info(
            "catalog updated to %s: %d catalog colors", export.version, len(export.variants)
        )

    def _record(self, started: datetime, result: SyncResult, **fields: str | None) -> None:
        with self._sessions() as session, session.begin():
            session.add(self._attempt(started, result, **fields))

    def _attempt(
        self,
        started: datetime,
        result: SyncResult,
        *,
        reason: str | None = None,
        version: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> CatalogSync:
        return CatalogSync(
            started_at=started,
            finished_at=self._clock(),
            result=result,
            reason=reason,
            dataset_version=version,
            etag=etag,
            last_modified=last_modified,
        )


def last_success(session: Session) -> CatalogSync | None:
    """The latest sync that worked (a new copy, or Not modified)."""
    return session.scalars(
        select(CatalogSync)
        .where(CatalogSync.result != SyncResult.FAILED)
        .order_by(CatalogSync.id.desc())
    ).first()


def _fits(value: str | None, length: int) -> str | None:
    """A header too long to keep is dropped: the next sync then downloads in full."""
    return value if value is not None and len(value) <= length else None
