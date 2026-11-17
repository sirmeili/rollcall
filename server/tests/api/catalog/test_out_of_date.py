"""After 14 days of failed syncs the catalog read says it may be out of date; failures stay
off Review and Home Assistant; and the scheduled syncs run with the server."""

import threading
from datetime import timedelta

import pytest
from api_helpers import admin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, refresh, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import CatalogSync, SyncResult
from filament_tracker.db.types import utcnow

CATALOG = "/api/v1/catalog"


def out_of_date(client: TestClient) -> bool:
    return client.get(CATALOG, headers=admin()).json()["out_of_date"]


def age_successes(db: Session, days: float) -> None:
    """Move every successful sync `days` into the past."""
    db.execute(
        update(CatalogSync)
        .where(CatalogSync.result != SyncResult.FAILED)
        .values(finished_at=utcnow() - timedelta(days=days))
    )
    db.commit()


def test_a_new_catalog_is_not_out_of_date(client: TestClient) -> None:
    assert out_of_date(client) is False
    refresh(client)
    assert out_of_date(client) is False


@pytest.mark.parametrize(("days", "expected"), [(13.9, False), (14, True), (30, True)])
def test_failures_for_14_days_since_the_last_success_make_it_out_of_date(
    client: TestClient, ofdb: FakeSource, db: Session, days: float, expected: bool
) -> None:
    refresh(client)
    ofdb.serve(status(503))
    refresh(client)

    age_successes(db, days)

    assert out_of_date(client) is expected


def test_a_successful_sync_ends_it(client: TestClient, ofdb: FakeSource, db: Session) -> None:
    refresh(client)
    ofdb.serve(status(503))
    refresh(client)
    age_successes(db, 20)
    assert out_of_date(client) is True

    ofdb.serve(status(304))
    refresh(client)

    assert out_of_date(client) is False


def test_an_old_success_is_not_out_of_date_until_a_sync_fails(
    client: TestClient, db: Session
) -> None:
    refresh(client)
    age_successes(db, 20)

    assert out_of_date(client) is False


def test_failed_syncs_stay_off_review_and_home_assistant(
    client: TestClient, ofdb: FakeSource
) -> None:
    before = client.get("/api/v1/review", headers=admin()).json()
    ofdb.serve(status(503))

    refresh(client)
    refresh(client)

    assert client.get("/api/v1/review", headers=admin()).json() == before
    # Home Assistant hears only of events and stock (ADR-0009); a sync writes neither.
    assert client.get("/api/v1/events", headers=admin()).json()["items"] == []
    assert client.get("/api/v1/inventory", headers=admin()).json() == []


def test_the_scheduled_syncs_run_with_the_server_and_stop_with_it(app: FastAPI) -> None:
    def running() -> bool:
        return any(t.name == "catalog-sync" for t in threading.enumerate())

    with TestClient(app, base_url="https://testserver", client=("192.168.1.20", 1)):
        assert running()

    assert not running()
