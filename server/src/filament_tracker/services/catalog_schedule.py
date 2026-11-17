"""Scheduled catalog syncs, in a background thread like the nightly backups (ADR-0005).

Daily syncs run at 04:00 in the server's time zone, after the 03:00 backup; weekly ones at
04:00 on Mondays; off schedules nothing, so only Refresh now contacts OFDB. When syncing is
on and the catalog has never synced, a new install syncs about a minute after it starts.
A failed sync is retried at the next scheduled run, with no extra retries. The settings are
read each time the thread wakes, so a change applies without a restart.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from filament_tracker.db.types import utcnow
from filament_tracker.services.catalog_sync import SyncBusy

logger = logging.getLogger(__name__)

SYNC_TIME = time(4, 0)
MONDAY = 0
# How long a new install waits before its first sync.
FIRST_SYNC_SECONDS = 60.0
# How often the scheduler wakes to notice a changed schedule or time zone.
CHECK_SECONDS = 3600.0


def next_sync(now: datetime, time_zone: str, schedule: str) -> datetime | None:
    """The next scheduled sync after `now`, in UTC; None when syncing is off."""
    if schedule == "off":
        return None
    zone = ZoneInfo(time_zone)
    local = now.astimezone(zone)
    day = local.date()
    if schedule == "weekly":
        day += timedelta(days=(MONDAY - day.weekday()) % 7)
    due = datetime.combine(day, SYNC_TIME, tzinfo=zone)
    if due <= local:
        step = 7 if schedule == "weekly" else 1
        due = datetime.combine(day + timedelta(days=step), SYNC_TIME, tzinfo=zone)
    return due.astimezone(UTC)


class Syncer(Protocol):
    def never_synced(self) -> bool: ...

    def sync(self) -> object: ...


class CatalogScheduler:
    def __init__(
        self,
        syncer: Syncer,
        *,
        schedule: Callable[[], str],
        time_zone: Callable[[], str],
        clock: Callable[[], datetime] = utcnow,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        self._syncer = syncer
        self._schedule = schedule
        self._time_zone = time_zone
        self._clock = clock
        self._stopped = threading.Event()
        # Waits up to the given seconds; True means stop.
        self._wait = wait or self._stopped.wait
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="catalog-sync", daemon=True)
        self._thread.start()
        logger.info("catalog sync: %s at 04:00 (%s)", self._schedule(), self._time_zone())

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(5)

    def run(self) -> None:
        if self._schedule() != "off" and self._syncer.never_synced():
            if self._wait(FIRST_SYNC_SECONDS):
                return
            if self._schedule() != "off":
                self._sync_once()
        while True:
            now = self._clock()
            due = self._next(now)
            while due is None or now < due:
                left = CHECK_SECONDS if due is None else (due - now).total_seconds()
                if self._wait(min(left, CHECK_SECONDS)):
                    return
                now = self._clock()
                if due is None or now < due:
                    # A schedule or time zone saved meanwhile moves the next sync.
                    due = self._next(now)
            self._sync_once()

    def _next(self, now: datetime) -> datetime | None:
        return next_sync(now, self._time_zone(), self._schedule())

    def _sync_once(self) -> None:
        """One sync. Its failures are recorded by the syncer and retried next time."""
        try:
            self._syncer.sync()
        except SyncBusy:
            logger.info("catalog sync skipped: one is already running")
        except Exception:
            logger.exception("catalog sync failed unexpectedly")
