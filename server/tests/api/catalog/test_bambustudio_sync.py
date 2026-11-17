"""The second source: BambuStudio's color code list, synced in the same run as OFDB, through
the API, with both faked. Each source succeeds or fails on its own."""

from typing import Any

import httpx
import pytest
from api_helpers import admin
from bambustudio_fake import BAMBUSTUDIO_ETAG, BAMBUSTUDIO_URL, body, color_codes, entry
from fastapi.testclient import TestClient
from ofdb_fake import LAST_MODIFIED, SYNC, Answer, FakeSource, ok, refresh, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import BambuColorCode
from filament_tracker.services import catalog_sync


def _codes(db: Session) -> set[tuple[str, str, str]]:
    db.expire_all()
    return {(c.bambu_code, c.filament_id, c.color_code) for c in db.scalars(select(BambuColorCode))}


def test_refresh_now_syncs_both_sources(
    client: TestClient, ofdb: FakeSource, bambustudio: FakeSource, db: Session
) -> None:
    result = refresh(client)

    assert result["ofdb"]["last_result"] == "updated"
    assert result["bambustudio"]["last_result"] == "updated"
    assert result["bambustudio"]["last_reason"] is None
    assert result["bambustudio"]["dataset_version"] is None
    assert result["bambustudio"]["last_success_at"] is not None
    assert len(ofdb.requests) == 1
    (request,) = bambustudio.requests
    assert str(request.url) == BAMBUSTUDIO_URL
    assert "If-None-Match" not in request.headers
    assert _codes(db) == {("10101", "GFA00", "K0"), ("99999", "GFA00", "Z9")}
    assert client.get(SYNC, headers=admin()).json() == result


def test_a_second_sync_asks_whether_the_list_changed_and_a_304_is_not_modified(
    client: TestClient, bambustudio: FakeSource, db: Session
) -> None:
    refresh(client)
    bambustudio.serve(status(304))

    second = refresh(client)

    request = bambustudio.requests[-1]
    assert request.headers["If-None-Match"] == BAMBUSTUDIO_ETAG
    assert request.headers["If-Modified-Since"] == LAST_MODIFIED
    assert second["bambustudio"]["last_result"] == "not_modified"
    assert len(_codes(db)) == 2
    refresh(client)
    assert bambustudio.requests[-1].headers["If-None-Match"] == BAMBUSTUDIO_ETAG


def test_a_changed_list_replaces_the_copy(
    client: TestClient, bambustudio: FakeSource, db: Session
) -> None:
    refresh(client)
    bambustudio.serve(ok(body(color_codes(entry("10102", "GFA01", "W1"))), etag='"bs-v2"'))

    assert refresh(client)["bambustudio"]["last_result"] == "updated"
    assert _codes(db) == {("10102", "GFA01", "W1")}


def _without(field: str) -> dict[str, Any]:
    data = color_codes()
    del data["data"][1][field]
    return data


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (httpx.ConnectError("refused"), "could not reach GitHub"),
        (httpx.ReadTimeout("slow"), "GitHub did not answer in time"),
        (httpx.RemoteProtocolError("closed early"), "download incomplete"),
        (status(404), "GitHub answered 404"),
        (ok(b'{"data": [{"fila_'), "the file is not valid JSON"),
        (ok(body([1, 2])), "the file's format changed"),
        (ok(body({"entries": []})), "the file's format changed"),
        (ok(body({"data": [], "total": 0})), "the file has no entries"),
        (ok(body(_without("fila_id"))), "the file has a missing field: fila_id"),
        (ok(body(_without("color_code"))), "the file has a missing field: color_code"),
        (ok(body(_without("fila_color_code"))), "the file has a missing field: fila_color_code"),
        (
            ok(body(color_codes(entry("10-1", "GFA00", "K0")))),
            "the file has a field that is not valid: fila_color_code",
        ),
    ],
)
def test_a_failed_list_keeps_the_last_good_copy_and_leaves_ofdb_alone(
    client: TestClient, bambustudio: FakeSource, db: Session, answer: Answer, reason: str
) -> None:
    first = refresh(client)
    bambustudio.serve(answer)

    failed = refresh(client)

    assert failed["bambustudio"]["last_result"] == "failed"
    assert failed["bambustudio"]["last_reason"] == reason
    assert failed["bambustudio"]["last_success_at"] == first["bambustudio"]["last_success_at"]
    assert failed["bambustudio"]["last_attempt_at"] > first["bambustudio"]["last_attempt_at"]
    assert len(_codes(db)) == 2
    # OFDB's attempt went ahead on its own.
    assert failed["ofdb"]["last_result"] == "updated"


def test_an_oversized_list_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog_sync, "MAX_BAMBUSTUDIO_BYTES", 100)

    failed = refresh(client)

    assert failed["bambustudio"]["last_reason"] == "download too large"
    assert failed["ofdb"]["last_result"] == "updated"


def test_an_ofdb_failure_does_not_stop_the_list(
    client: TestClient, ofdb: FakeSource, db: Session
) -> None:
    ofdb.serve(status(500))

    result = refresh(client)

    assert result["ofdb"]["last_result"] == "failed"
    assert result["bambustudio"]["last_result"] == "updated"
    assert len(_codes(db)) == 2


def test_a_304_to_a_request_that_did_not_ask_fails(
    client: TestClient, bambustudio: FakeSource
) -> None:
    bambustudio.serve(status(304))

    assert refresh(client)["bambustudio"]["last_reason"] == "GitHub answered 304"


def test_an_install_whose_list_never_synced_counts_as_never_synced(
    client: TestClient, bambustudio: FakeSource
) -> None:
    # An install upgraded from before the list existed syncs a minute after it starts.
    syncer: catalog_sync.CatalogSyncer = client.app.state.catalog  # type: ignore[attr-defined]
    bambustudio.serve(status(500))
    refresh(client)

    assert syncer.never_synced() is True
    bambustudio.serve(ok(body(color_codes())))
    refresh(client)
    assert syncer.never_synced() is False
