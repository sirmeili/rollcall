"""Scheduled catalog syncs: 04:00 in the time zone, daily or on Mondays, off, and a first
sync shortly after a new install starts. A fake clock and a fake syncer, so nothing is
downloaded."""

from datetime import UTC, datetime

import pytest

from filament_tracker.services.catalog_schedule import (
    CHECK_SECONDS,
    FIRST_SYNC_SECONDS,
    CatalogScheduler,
    next_sync,
)
from filament_tracker.services.catalog_sync import SyncBusy


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


# --- When the next sync is ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "zone", "expected"),
    [
        # Before 04:00: today; at or after: tomorrow.
        ("2026-11-10T08:00:00Z", "America/New_York", "2026-11-10T09:00:00Z"),
        ("2026-11-10T09:00:00Z", "America/New_York", "2026-11-11T09:00:00Z"),
        ("2026-11-10T12:00:00Z", "UTC", "2026-11-11T04:00:00Z"),
        # Across the end of daylight saving time (Nov 1, 2026): 04:00 EST is 09:00 UTC.
        ("2026-10-31T12:00:00Z", "America/New_York", "2026-11-01T09:00:00Z"),
        # Across its start (Mar 8, 2026): 04:00 EDT is 08:00 UTC.
        ("2026-03-07T12:00:00Z", "America/New_York", "2026-03-08T08:00:00Z"),
    ],
)
def test_daily_syncs_are_at_four_in_the_time_zone(now: str, zone: str, expected: str) -> None:
    assert next_sync(at(now), zone, "daily") == at(expected)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Tuesday Nov 10, 2026: the next Monday.
        ("2026-11-10T12:00:00Z", "2026-11-16T04:00:00Z"),
        # Monday before 04:00: that morning; after: a week on.
        ("2026-11-16T03:59:00Z", "2026-11-16T04:00:00Z"),
        ("2026-11-16T04:00:00Z", "2026-11-23T04:00:00Z"),
        # Sunday.
        ("2026-11-15T23:00:00Z", "2026-11-16T04:00:00Z"),
    ],
)
def test_weekly_syncs_are_on_mondays_at_four(now: str, expected: str) -> None:
    assert next_sync(at(now), "UTC", "weekly") == at(expected)


def test_weekly_uses_monday_in_the_time_zone() -> None:
    # 02:00 UTC Monday is still Sunday evening in New York.
    assert next_sync(at("2026-11-16T02:00:00Z"), "America/New_York", "weekly") == at(
        "2026-11-16T09:00:00Z"
    )


def test_off_schedules_nothing() -> None:
    assert next_sync(at("2026-11-10T12:00:00Z"), "UTC", "off") is None


# --- The scheduler --------------------------------------------------------------------------


class FakeSyncer:
    def __init__(self, synced: bool = True, busy: bool = False) -> None:
        self.synced = synced
        self.busy = busy
        self.syncs: list[datetime] = []
        self.clock = None

    def never_synced(self) -> bool:
        return not self.synced

    def sync(self) -> None:
        assert self.clock is not None
        self.syncs.append(self.clock())
        self.synced = True
        if self.busy:
            raise SyncBusy


class Settings:
    def __init__(self, schedule: str = "daily", zone: str = "UTC") -> None:
        self.schedule = schedule
        self.zone = zone


class FakeTime:
    """A clock that moves only when the scheduler waits; stops after `syncs` syncs, or
    after `limit` waits."""

    def __init__(self, start: str, syncer: FakeSyncer, syncs: int, limit: int = 1000) -> None:
        self.now = at(start)
        self.waits: list[float] = []
        self.syncer = syncer
        self.syncs = syncs
        self.limit = limit
        self.on_wait: list = []

    def clock(self) -> datetime:
        return self.now

    def wait(self, seconds: float) -> bool:
        if len(self.syncer.syncs) >= self.syncs or len(self.waits) >= self.limit:
            return True
        self.waits.append(seconds)
        self.now = datetime.fromtimestamp(self.now.timestamp() + seconds, UTC)
        for hook in self.on_wait:
            hook(self)
        return False


def _scheduler(
    start: str, syncer: FakeSyncer, settings: Settings, syncs: int, limit: int = 1000
) -> tuple[CatalogScheduler, FakeTime]:
    fake = FakeTime(start, syncer, syncs, limit)
    syncer.clock = fake.clock
    scheduler = CatalogScheduler(
        syncer,
        schedule=lambda: settings.schedule,
        time_zone=lambda: settings.zone,
        clock=fake.clock,
        wait=fake.wait,
    )
    return scheduler, fake


def test_daily_syncs_run_each_morning_at_four() -> None:
    syncer = FakeSyncer()
    scheduler, fake = _scheduler("2026-11-09T20:00:00Z", syncer, Settings(), syncs=3)

    scheduler.run()

    assert syncer.syncs == [at(f"2026-11-{d}T04:00:00Z") for d in (10, 11, 12)]
    # It wakes at least hourly, to notice a changed setting.
    assert max(fake.waits) == CHECK_SECONDS


def test_weekly_syncs_run_on_mondays() -> None:
    syncer = FakeSyncer()
    scheduler, _ = _scheduler("2026-11-10T12:00:00Z", syncer, Settings("weekly"), syncs=2)

    scheduler.run()

    assert syncer.syncs == [at("2026-11-16T04:00:00Z"), at("2026-11-23T04:00:00Z")]


def test_off_never_syncs() -> None:
    syncer = FakeSyncer(synced=False)
    scheduler, fake = _scheduler("2026-11-10T12:00:00Z", syncer, Settings("off"), 1, limit=500)

    scheduler.run()

    assert syncer.syncs == []
    assert len(fake.waits) == 500


def test_turning_it_on_takes_effect_without_a_restart() -> None:
    syncer = FakeSyncer()
    settings = Settings("off")
    scheduler, fake = _scheduler("2026-11-10T12:00:00Z", syncer, settings, syncs=1)

    def switch_on(time: FakeTime) -> None:
        if time.now >= at("2026-11-11T00:00:00Z"):
            settings.schedule = "daily"

    fake.on_wait.append(switch_on)
    scheduler.run()

    assert syncer.syncs == [at("2026-11-11T04:00:00Z")]


def test_a_new_install_syncs_about_a_minute_after_starting() -> None:
    syncer = FakeSyncer(synced=False)
    scheduler, fake = _scheduler("2026-11-10T12:00:00Z", syncer, Settings(), syncs=2)

    scheduler.run()

    assert fake.waits[0] == FIRST_SYNC_SECONDS == 60
    assert syncer.syncs == [at("2026-11-10T12:01:00Z"), at("2026-11-11T04:00:00Z")]


def test_a_new_install_with_syncing_off_does_not_sync() -> None:
    syncer = FakeSyncer(synced=False)
    scheduler, _ = _scheduler("2026-11-10T12:00:00Z", syncer, Settings("off"), 1, limit=50)

    scheduler.run()

    assert syncer.syncs == []


def test_a_catalog_already_synced_waits_for_the_schedule() -> None:
    syncer = FakeSyncer(synced=True)
    scheduler, _ = _scheduler("2026-11-10T12:00:00Z", syncer, Settings(), syncs=1)

    scheduler.run()

    assert syncer.syncs == [at("2026-11-11T04:00:00Z")]


def test_a_busy_sync_is_left_to_the_next_run() -> None:
    syncer = FakeSyncer(busy=True)
    scheduler, _ = _scheduler("2026-11-10T12:00:00Z", syncer, Settings(), syncs=2)

    scheduler.run()

    # No extra retries: the next attempt is the next scheduled run.
    assert syncer.syncs == [at("2026-11-11T04:00:00Z"), at("2026-11-12T04:00:00Z")]


def test_an_unexpected_error_does_not_stop_the_schedule(caplog: pytest.LogCaptureFixture) -> None:
    syncer = FakeSyncer()
    calls: list[datetime] = []

    def broken() -> None:
        calls.append(syncer.clock())
        syncer.syncs.append(syncer.clock())
        raise RuntimeError("disk full")

    syncer.sync = broken  # type: ignore[method-assign]
    scheduler, _ = _scheduler("2026-11-10T12:00:00Z", syncer, Settings(), syncs=2)

    scheduler.run()

    assert len(calls) == 2
    assert "catalog sync failed unexpectedly" in caplog.text


def test_start_and_stop_run_a_real_thread() -> None:
    scheduler = CatalogScheduler(FakeSyncer(), schedule=lambda: "off", time_zone=lambda: "UTC")

    scheduler.start()
    scheduler.stop()

    assert scheduler._thread is not None  # noqa: SLF001
    assert not scheduler._thread.is_alive()  # noqa: SLF001
