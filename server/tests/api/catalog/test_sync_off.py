"""Catalog syncing set to Off: the scheduler never contacts OFDB or BambuStudio's list, even
on a new install that has never synced."""

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource

from filament_tracker.services.catalog_schedule import CatalogScheduler


def test_off_never_contacts_either_source(
    app: FastAPI, client: TestClient, ofdb: FakeSource, bambustudio: FakeSource
) -> None:
    now = datetime(2026, 11, 10, 12, tzinfo=UTC)
    waits: list[float] = []

    def wait(seconds: float) -> bool:
        waits.append(seconds)
        return len(waits) >= 200

    scheduler = CatalogScheduler(
        app.state.catalog,
        schedule=lambda: "off",
        time_zone=lambda: "UTC",
        clock=lambda: now,
        wait=wait,
    )
    assert app.state.catalog.never_synced()

    scheduler.run()

    assert len(waits) == 200
    assert ofdb.requests == []
    assert bambustudio.requests == []
