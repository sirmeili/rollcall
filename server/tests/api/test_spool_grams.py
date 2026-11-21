"""Net weight and grams left on spools (#160): set from tags, Received, the AMS and by hand."""

from datetime import UTC, datetime

import pytest
from api_helpers import CSRF, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import (
    CatalogBrand,
    CatalogFilament,
    CatalogSize,
    CatalogVariant,
)
from filament_tracker.db.models import Printer
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.ams import ingest

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def viewer(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.VIEWER, username="viewer")


def test_a_received_scan_sets_net_weight_from_the_tag_and_grams_left_to_it(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    spool_id = scan(client, token, SyntheticTag(spool_weight_g=750), "received")["spool"]["id"]

    detail = viewer.get(f"/api/v1/spools/{spool_id}").json()

    assert (detail["net_weight_g"], detail["grams_left_g"]) == (750, 750)


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR, username="editor")


def _product(editor: TestClient) -> int:
    body = {"display_name": "TPU Red", "filament_type": "TPU", "color_rgba": "FF0000FF"}
    response = editor.post("/api/v1/products", json=body, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _placeholder(editor: TestClient, product_id: int) -> dict:
    response = editor.post("/api/v1/spools", json={"product_id": product_id}, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


def _catalog_color(db: Session, *weights: float) -> str:
    """A catalog color sold in the given sizes."""
    db.add(CatalogBrand(uuid="b", name="Bambu Lab", moved_from=[]))
    db.flush()
    db.add(CatalogFilament(uuid="f", brand_uuid="b", position=0, name="TPU", material="TPU"))
    db.flush()
    db.add(CatalogVariant(uuid="v", filament_uuid="f", position=0, name="Red", color_hex="FF0000"))
    db.flush()
    for n, weight in enumerate(weights):
        db.add(CatalogSize(uuid=f"s{n}", variant_uuid="v", filament_weight=weight))
    db.commit()
    return "v"


def _link(editor: TestClient, product_id: int, color: str) -> None:
    response = editor.patch(
        f"/api/v1/products/{product_id}", json={"catalog_color": color}, headers=CSRF
    )
    assert response.status_code == 200, response.text


def test_a_placeholder_with_no_catalog_color_holds_1000_g(editor: TestClient) -> None:
    spool = _placeholder(editor, _product(editor))

    assert (spool["net_weight_g"], spool["grams_left_g"]) == (1000, 1000)


def test_a_placeholder_takes_its_catalog_colors_only_size(editor: TestClient, db: Session) -> None:
    product_id = _product(editor)
    _link(editor, product_id, _catalog_color(db, 500.0))

    spool = _placeholder(editor, product_id)

    assert (spool["net_weight_g"], spool["grams_left_g"]) == (500, 500)


def test_a_placeholder_whose_color_has_several_sizes_holds_1000_g(
    editor: TestClient, db: Session
) -> None:
    product_id = _product(editor)
    _link(editor, product_id, _catalog_color(db, 500.0, 250.0))

    assert _placeholder(editor, product_id)["net_weight_g"] == 1000


def test_a_placeholder_whose_color_has_several_sizes_of_one_weight_takes_it(
    editor: TestClient, db: Session
) -> None:
    product_id = _product(editor)
    _link(editor, product_id, _catalog_color(db, 500.0, 500.0))

    assert _placeholder(editor, product_id)["net_weight_g"] == 500


def test_scanning_a_placeholders_tag_replaces_the_fallback_with_the_tag_weight(
    client: TestClient, token: str, editor: TestClient, viewer: TestClient
) -> None:
    tag = SyntheticTag(spool_weight_g=750, filament_type="TPU", color_rgba="FF0000FF")
    placeholder = _placeholder(editor, _product(editor))

    result = scan(client, token, tag, "received")

    detail = viewer.get(f"/api/v1/spools/{placeholder['id']}").json()
    assert result["spool"]["id"] == placeholder["id"]
    assert (detail["net_weight_g"], detail["grams_left_g"]) == (750, 750)


def test_a_tag_without_a_weight_takes_the_fallback(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    spool_id = scan(client, token, SyntheticTag(spool_weight_g=0), "received")["spool"]["id"]

    detail = viewer.get(f"/api/v1/spools/{spool_id}").json()

    assert (detail["net_weight_g"], detail["grams_left_g"]) == (1000, 1000)


def test_a_spool_first_scanned_as_opened_is_full(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    spool_id = scan(client, token, SyntheticTag(spool_weight_g=750), "opened")["spool"]["id"]

    detail = viewer.get(f"/api/v1/spools/{spool_id}").json()

    assert (detail["state"], detail["net_weight_g"], detail["grams_left_g"]) == ("open", 750, 750)


def test_opening_a_received_spool_keeps_its_grams_left(
    client: TestClient, token: str, admin_user: TestClient
) -> None:
    tag = SyntheticTag(spool_weight_g=750)
    spool_id = scan(client, token, tag, "received")["spool"]["id"]
    _edit(admin_user, spool_id, {"grams_left_g": 600})

    scan(client, token, tag, "opened")

    detail = admin_user.get(f"/api/v1/spools/{spool_id}").json()
    assert (detail["state"], detail["grams_left_g"]) == ("open", 600)


# --- Editing by hand -------------------------------------------------------------------------


@pytest.fixture
def admin_user(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.ADMIN, username="admin")


@pytest.fixture
def spool_id(client: TestClient, token: str) -> int:
    return scan(client, token, SyntheticTag(spool_weight_g=1000), "received")["spool"]["id"]


def _edit(user: TestClient, spool_id: int, body: dict) -> tuple[int, dict]:
    response = user.patch(f"/api/v1/spools/{spool_id}", json=body, headers=CSRF)
    return response.status_code, response.json()


def test_an_admin_edits_net_weight_and_grams_left(admin_user: TestClient, spool_id: int) -> None:
    status, detail = _edit(admin_user, spool_id, {"net_weight_g": 500, "grams_left_g": 120})

    assert status == 200
    assert (detail["net_weight_g"], detail["grams_left_g"]) == (500, 120)


def test_grams_edits_write_no_event_and_leave_nothing_to_undo(
    admin_user: TestClient, spool_id: int
) -> None:
    before = admin_user.get(f"/api/v1/spools/{spool_id}").json()["events"]

    _, detail = _edit(admin_user, spool_id, {"grams_left_g": 300})

    assert detail["events"] == before
    undo = admin_user.post(f"/api/v1/events/{before[0]['id']}/revert", headers=CSRF)
    assert undo.status_code == 200
    assert admin_user.get(f"/api/v1/spools/{spool_id}").json()["grams_left_g"] == 300


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"net_weight_g": 0}, "net_weight_g"),
        ({"net_weight_g": 10_001}, "net_weight_g"),
        ({"net_weight_g": None}, "net_weight_g"),
        ({"grams_left_g": -1}, "grams_left_g"),
        ({"grams_left_g": 1001}, "grams_left_g"),
        ({"grams_left_g": None}, "grams_left_g"),
        ({"net_weight_g": 400, "grams_left_g": 401}, "grams_left_g"),
    ],
)
def test_out_of_range_grams_are_refused_with_a_message(
    admin_user: TestClient, spool_id: int, body: dict, field: str
) -> None:
    status, answer = _edit(admin_user, spool_id, body)

    assert status == 422
    assert answer["detail"]["problems"][field]
    detail = admin_user.get(f"/api/v1/spools/{spool_id}").json()
    assert (detail["net_weight_g"], detail["grams_left_g"]) == (1000, 1000)


def test_the_net_weight_limits_are_allowed(admin_user: TestClient, spool_id: int) -> None:
    assert _edit(admin_user, spool_id, {"net_weight_g": 10_000})[0] == 200
    status, detail = _edit(admin_user, spool_id, {"net_weight_g": 1, "grams_left_g": 0})
    assert (status, detail["net_weight_g"], detail["grams_left_g"]) == (200, 1, 0)


@pytest.mark.parametrize(
    ("role", "requester"),
    [(Role.EDITOR, False), (Role.VIEWER, False), (Role.VIEWER, True)],
)
def test_only_admins_edit_grams(
    app: FastAPI, client: TestClient, spool_id: int, role: Role, requester: bool
) -> None:
    user = signed_in(app, role, username="someone", requester=requester)

    for body in ({"net_weight_g": 500}, {"grams_left_g": 10}):
        assert _edit(user, spool_id, body)[0] == 403, body
    detail = user.get(f"/api/v1/spools/{spool_id}").json()
    assert (detail["net_weight_g"], detail["grams_left_g"]) == (1000, 1000)


def test_an_editor_still_edits_location(app: FastAPI, client: TestClient, spool_id: int) -> None:
    editor = signed_in(app, Role.EDITOR, username="someone")

    assert _edit(editor, spool_id, {"location": "Shelf B"})[1]["location"] == "Shelf B"


# --- From the AMS ----------------------------------------------------------------------------

UID = "A1B2C3D4E5F60718293A4B5C6D7E8F90"


def _ams_reports(db: Session, pct: int | None, when: datetime = T0) -> None:
    printer = db.scalar(select(Printer)) or Printer(
        name="P1S", serial="01P00A000000001", host="192.168.1.40"
    )
    db.add(printer)
    ingest(db, printer, [TrayReport(0, 0, UID, "GFA00", "PLA", "PLA Basic", "000000FF", pct)], when)
    db.commit()


def _scanned(client: TestClient, token: str, weight: int = 750) -> int:
    tag = SyntheticTag(spool_weight_g=weight, tray_uid=bytes.fromhex(UID))
    return scan(client, token, tag, "received")["spool"]["id"]


def test_an_ams_report_sets_grams_left_from_the_remaining_pct(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    spool_id = _scanned(client, token)

    _ams_reports(db, 40)

    detail = viewer.get(f"/api/v1/spools/{spool_id}").json()
    assert (detail["state"], detail["net_weight_g"], detail["grams_left_g"]) == ("open", 750, 300)


def test_the_latest_ams_report_wins_over_a_hand_figure(
    client: TestClient, token: str, admin_user: TestClient, db: Session
) -> None:
    spool_id = _scanned(client, token)
    _ams_reports(db, 40)
    _edit(admin_user, spool_id, {"grams_left_g": 500})

    _ams_reports(db, 20)

    assert admin_user.get(f"/api/v1/spools/{spool_id}").json()["grams_left_g"] == 150


def test_a_spool_the_ams_sees_first_takes_the_fallback_net_weight(
    viewer: TestClient, db: Session
) -> None:
    _ams_reports(db, 50)

    [row] = viewer.get("/api/v1/spools").json()["items"]
    assert (row["net_weight_g"], row["grams_left_g"]) == (1000, 500)


def test_a_spool_the_ams_sees_first_without_a_remaining_pct_has_unknown_grams_left(
    viewer: TestClient, db: Session
) -> None:
    _ams_reports(db, None)

    [row] = viewer.get("/api/v1/spools").json()["items"]
    assert (row["state"], row["net_weight_g"], row["grams_left_g"]) == ("open", 1000, None)
