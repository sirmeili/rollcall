"""Catalog sync through the API: Refresh now and the sync status (Admin only), with OFDB
faked by an injected httpx transport."""

import gzip
from types import ModuleType

import httpx
import pytest
from api_helpers import (
    BASE_URL,
    CSRF,
    INTERNET_CLIENT,
    admin,
    scan,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import (
    BAMBU,
    ETAG,
    LAST_MODIFIED,
    SYNC,
    Answer,
    FakeSource,
    changed_export,
    export,
    gz,
    ok,
    refresh,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import (
    CatalogBrand,
    CatalogFilament,
    CatalogSize,
    CatalogVariant,
)
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role
from filament_tracker.services import catalog_export, catalog_sync

INVENTORY = ("/api/v1/products", "/api/v1/spools", "/api/v1/events", "/api/v1/inventory")


# --- A sync ------------------------------------------------------------------------------


def test_refresh_now_stores_bambu_lab_only(client: TestClient, db: Session) -> None:
    result = refresh(client)

    assert result["ofdb"]["last_result"] == "updated"
    assert result["ofdb"]["dataset_version"] == "2026.11.14"
    assert result["colors"] == 4
    assert [b.name for b in db.scalars(select(CatalogBrand))] == ["Bambu Lab"]
    lines = db.scalars(select(CatalogFilament).order_by(CatalogFilament.position)).all()
    assert [(f.name, f.material) for f in lines] == [("PLA Basic", "PLA"), ("PETG HF", "PETG")]
    assert lines[0].density == 1.26
    assert lines[0].min_print_temperature == 190
    assert lines[1].moved_from == ["old-petg-uuid"]
    colors = {v.uuid: v for v in db.scalars(select(CatalogVariant))}
    assert set(colors) == {"var-black", "var-jade", "var-gradient", "var-cream"}
    assert colors["var-jade"].color_hex == "FFFFFF"
    assert colors["var-gradient"].extra_hexes == ["FFFFFF"]
    assert colors["var-cream"].discontinued is True
    assert colors["var-cream"].moved_from == ["x"]
    sizes = {s.uuid: s for s in db.scalars(select(CatalogSize))}
    assert set(sizes) == {"size-black-refill", "size-black-spool"}
    assert sizes["size-black-refill"].refill is True
    assert sizes["size-black-refill"].article_number == "10101"
    assert sizes["size-black-refill"].filament_weight == 1000
    assert sizes["size-black-refill"].purchase_links == [
        {"store": "Bambu Lab US", "url": "https://store.example/black-refill"}
    ]
    assert sizes["size-black-spool"].refill is False
    assert sizes["size-black-spool"].purchase_links == []


def test_status_before_any_sync(client: TestClient) -> None:
    response = client.get(SYNC, headers=admin())

    assert response.status_code == 200
    never = {
        "last_success_at": None,
        "last_attempt_at": None,
        "last_result": None,
        "last_reason": None,
        "dataset_version": None,
    }
    assert response.json() == {"colors": 0, "ofdb": never, "bambustudio": never}


def test_the_status_reports_the_last_sync(client: TestClient) -> None:
    result = refresh(client)

    assert client.get(SYNC, headers=admin()).json() == result


def test_the_first_sync_asks_for_the_whole_export(client: TestClient, ofdb: FakeSource) -> None:
    refresh(client)

    (request,) = ofdb.requests
    assert str(request.url) == "https://api.openfilamentdatabase.org/json/all.json.gz"
    assert "If-None-Match" not in request.headers
    assert "If-Modified-Since" not in request.headers


def test_a_second_sync_asks_whether_it_changed_and_a_304_is_not_modified(
    client: TestClient, ofdb: FakeSource
) -> None:
    first = refresh(client)
    ofdb.serve(status(304))

    second = refresh(client)

    request = ofdb.requests[-1]
    assert request.headers["If-None-Match"] == ETAG
    assert request.headers["If-Modified-Since"] == LAST_MODIFIED
    assert second["ofdb"]["last_result"] == "not_modified"
    assert second["ofdb"]["last_reason"] is None
    assert second["ofdb"]["dataset_version"] == "2026.11.14"
    assert second["colors"] == 4
    assert second["ofdb"]["last_success_at"] >= first["ofdb"]["last_success_at"]
    assert second["ofdb"]["last_attempt_at"] == second["ofdb"]["last_success_at"]
    # A 304 keeps the headers, so the next sync asks the same question.
    refresh(client)
    assert ofdb.requests[-1].headers["If-None-Match"] == ETAG


def test_a_changed_export_replaces_the_catalog(
    client: TestClient, ofdb: FakeSource, db: Session
) -> None:
    refresh(client)
    ofdb.serve(ok(gz(changed_export()), etag='"v2-etag"'))

    result = refresh(client)

    assert result["ofdb"]["last_result"] == "updated"
    assert result["ofdb"]["dataset_version"] == "2026.11.15"
    assert set(db.scalars(select(CatalogVariant.name))) == {
        "Black",
        "Arctic Whisper",
        "Cream",
        "Red",
    }
    refresh(client)
    assert ofdb.requests[-1].headers["If-None-Match"] == '"v2-etag"'


# --- Failures ----------------------------------------------------------------------------


def _missing(table: str, field: str) -> bytes:
    data = export("2026.11.15")
    del data[table][1][field]
    return gz(data)


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (httpx.ConnectError("refused"), "could not reach OFDB"),
        (httpx.ReadTimeout("slow"), "OFDB did not answer in time"),
        (httpx.RemoteProtocolError("closed early"), "download incomplete"),
        (status(500), "OFDB answered 500"),
        (ok(gz(export())[:-40]), "download incomplete"),
        (ok(b"not gzip at all"), "download is not a valid gzip file"),
        (ok(gzip.compress(b"{not json")), "export is not valid JSON"),
        (ok(gz([1, 2])), "export is not a JSON object"),
        (ok(gz({**export(), "version": None})), "export has no version"),
        (ok(gz({**export(), "variants": {}})), "export has no variants list"),
        (ok(gz({**export(), "brands": []})), "export has no Bambu Lab brand"),
        (ok(_missing("variants", "color_hex")), "export has a missing field: variants.color_hex"),
        (ok(_missing("filaments", "material")), "export has a missing field: filaments.material"),
        (ok(_missing("sizes", "discontinued")), "export has a missing field: sizes.discontinued"),
    ],
)
def test_a_failed_sync_keeps_the_previous_catalog(
    client: TestClient, ofdb: FakeSource, db: Session, answer: Answer, reason: str
) -> None:
    first = refresh(client)
    ofdb.serve(answer)

    failed = refresh(client)

    assert failed["ofdb"]["last_result"] == "failed"
    assert failed["ofdb"]["last_reason"] == reason
    assert failed["ofdb"]["last_success_at"] == first["ofdb"]["last_success_at"]
    assert failed["ofdb"]["last_attempt_at"] > first["ofdb"]["last_attempt_at"]
    assert failed["ofdb"]["dataset_version"] == "2026.11.14"
    assert failed["colors"] == 4
    assert len(db.scalars(select(CatalogVariant)).all()) == 4


@pytest.mark.parametrize(
    ("module", "limit", "reason"),
    [
        (catalog_sync, "MAX_DOWNLOAD_BYTES", "download too large"),
        (catalog_export, "MAX_JSON_BYTES", "export too large"),
    ],
)
def test_an_oversized_export_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    limit: str,
    reason: str,
) -> None:
    monkeypatch.setattr(module, limit, 100)

    failed = refresh(client)

    assert failed["ofdb"]["last_reason"] == reason
    assert failed["colors"] == 0


def test_a_malformed_hex_fails_the_sync(client: TestClient, ofdb: FakeSource) -> None:
    data = export()
    data["variants"][0]["color_hex"] = "black"
    ofdb.serve(ok(gz(data)))

    failed = refresh(client)

    assert failed["ofdb"]["last_reason"] == "export has a not valid field: variants.color_hex"
    assert failed["colors"] == 0
    assert failed["ofdb"]["last_success_at"] is None


def test_an_export_without_bambu_lab_lines_fails(client: TestClient, ofdb: FakeSource) -> None:
    data = export()
    data["filaments"] = [f for f in data["filaments"] if f["brand_id"] != f"id-{BAMBU}"]
    ofdb.serve(ok(gz(data)))

    assert refresh(client)["ofdb"]["last_reason"] == "export has no Bambu Lab filament lines"


def test_an_export_repeating_a_uuid_fails(client: TestClient, ofdb: FakeSource) -> None:
    data = export()
    data["variants"][1]["uuid"] = data["variants"][0]["uuid"]
    ofdb.serve(ok(gz(data)))

    assert refresh(client)["ofdb"]["last_reason"] == "export repeats a UUID in variants"


def test_an_export_repeating_an_id_fails(client: TestClient, ofdb: FakeSource) -> None:
    data = export()
    data["variants"][1]["id"] = data["variants"][0]["id"]
    ofdb.serve(ok(gz(data)))

    assert refresh(client)["ofdb"]["last_reason"] == "export repeats an id in variants"


def test_a_304_to_a_request_that_did_not_ask_fails(client: TestClient, ofdb: FakeSource) -> None:
    ofdb.serve(status(304))

    assert refresh(client)["ofdb"]["last_reason"] == "OFDB answered 304"


# --- What a sync must not do -------------------------------------------------------------


def test_a_sync_leaves_products_spools_tags_and_events_alone(
    client: TestClient, token: str, ofdb: FakeSource
) -> None:
    scan(client, token, SyntheticTag(), "received")
    scan(client, token, SyntheticTag(color_rgba="FFFFFFFF"), "received")
    before = {path: client.get(path, headers=admin()).json() for path in INVENTORY}

    refresh(client)
    ofdb.serve(ok(gz(changed_export()), etag='"v2"'))
    refresh(client)

    assert {path: client.get(path, headers=admin()).json() for path in INVENTORY} == before


def test_refresh_now_during_a_sync_never_starts_a_second_one(
    client: TestClient, ofdb: FakeSource
) -> None:
    during: list[int] = []
    body = gz(export())

    def slow_ofdb(request: httpx.Request) -> httpx.Response:
        # A second Refresh now arrives while this sync is still downloading.
        during.append(client.post(SYNC, headers=admin()).status_code)
        return ok(body)(request)

    ofdb.serve(slow_ofdb)

    assert refresh(client)["ofdb"]["last_result"] == "updated"
    assert during == [409]
    assert len(ofdb.requests) == 1


# --- Who may ------------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("role", [Role.VIEWER, Role.EDITOR])
def test_only_admins_see_the_status_and_refresh(
    app: FastAPI, client: TestClient, ofdb: FakeSource, method: str, role: Role
) -> None:
    user = signed_in(app, role)

    response = user.request(method.upper(), SYNC, headers=CSRF)

    assert response.status_code == 403
    assert ofdb.requests == []


def test_an_admin_signed_in_can_refresh(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.ADMIN)

    assert user.post(SYNC).status_code == 403  # a cookie write needs the CSRF header
    assert user.post(SYNC, headers=CSRF).json()["ofdb"]["last_result"] == "updated"
    assert user.get(SYNC).json()["ofdb"]["last_result"] == "updated"


def test_bearer_tokens_from_the_internet_are_refused(
    app: FastAPI, client: TestClient, ofdb: FakeSource
) -> None:
    outside = TestClient(app, base_url=BASE_URL, client=INTERNET_CLIENT)

    assert outside.post(SYNC, headers=admin()).status_code in (401, 403)
    assert ofdb.requests == []
