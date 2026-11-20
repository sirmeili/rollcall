"""Waiting requests retry by themselves: when stock changes, Approved and Waiting on Filament
requests take more holds, in Active-tab order, and a covered one moves to Queued with no
person and no email. Spools that are gone stop counting."""

from datetime import UTC, datetime
from typing import Any

import pytest
from api_helpers import CSRF, bearer, scan
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from request_helpers import JADE_WHITE, REQUESTS, person, put_in, stock, submitted
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Printer
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.ams import ingest

BLACK_PLA = "000000FF"
TRAY_UID = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
T0 = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _read(user: TestClient, request_id: int) -> dict[str, Any]:
    return user.get(f"{REQUESTS}/{request_id}").json()


def _move(
    user: TestClient,
    request_id: int,
    from_status: str,
    to_status: str,
    grams: dict[str, int] | None = None,
) -> Response:
    body: dict[str, Any] = {"from_status": from_status, "to_status": to_status, "note": ""}
    if grams is not None:
        body["grams"] = grams
    return user.post(f"{REQUESTS}/{request_id}/moves", json=body, headers=CSRF)


def _approved(
    sam: TestClient, frank: TestClient, choice: dict[str, Any], grams: int, **overrides: Any
) -> dict[str, Any]:
    """A request of sam's for one filament choice, approved with `grams`; as Approve left it."""
    created = submitted(sam, choices=[{**choice, "note": ""}], **overrides)
    [shown] = created["choices"]
    response = _move(frank, created["id"], "submitted", "approved", {str(shown["id"]): grams})
    assert response.status_code == 200, response.text
    return response.json()


def _waiting(
    sam: TestClient, frank: TestClient, product_id: int, grams: int, **overrides: Any
) -> dict[str, Any]:
    read = _approved(sam, frank, {"product_id": product_id}, grams, **overrides)
    assert read["status"] == "waiting_on_filament", read
    return read


def _moved_automatically(frank: TestClient, request_id: int) -> dict[str, Any]:
    """The request, checked to be Queued by an automatic move from Waiting on Filament."""
    read = _read(frank, request_id)
    assert read["status"] == "queued"
    entry = read["history"][0]
    assert (
        entry["username"],
        entry["from_value"],
        entry["to_value"],
        entry["automatic"],
    ) == (None, "waiting_on_filament", "queued", True)
    return read


def _short(read: dict[str, Any]) -> int:
    [choice] = read["choices"]
    return choice["short_g"]


# --- Triggers ---------------------------------------------------------------------------------


def test_a_received_spool_queues_a_waiting_request_with_no_email(
    app: FastAPI,
    client: TestClient,
    token: str,
    sam: TestClient,
    frank: TestClient,
    outbox: FakeOutbox,
) -> None:
    email_on(client)
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _waiting(sam, frank, pla, 1500)
    assert _short(waiting) == 500
    sent(app, outbox)

    stock(client, token, BLACK_PLA, "PLA", "received")

    read = _moved_automatically(frank, waiting["id"])
    assert _short(read) == 0
    assert sent(app, outbox) == []


def test_a_spool_first_scanned_as_opened_queues_a_waiting_request(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _waiting(sam, frank, pla, 1500)

    stock(client, token, BLACK_PLA, "PLA", "opened")

    _moved_automatically(frank, waiting["id"])


def _holds(read: dict[str, Any]) -> list[tuple[int, int]]:
    [choice] = read["choices"]
    return [(hold["spool_id"], hold["grams"]) for hold in choice["holds"]]


def _edit_spool(frank: TestClient, spool_id: int, body: dict[str, int]) -> None:
    response = frank.patch(f"/api/v1/spools/{spool_id}", json=body, headers=CSRF)
    assert response.status_code == 200, response.text


def test_a_hand_edit_of_grams_queues_a_waiting_request_holding_more_on_the_same_spool(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _waiting(sam, frank, pla, 1500)
    [(spool_id, _)] = _holds(waiting)

    _edit_spool(frank, spool_id, {"net_weight_g": 2000, "grams_left_g": 2000})

    read = _moved_automatically(frank, waiting["id"])
    assert _holds(read) == [(spool_id, 1500)]


def _ams_reports(db: Session, pct: int) -> None:
    """The printer link's report of the AMS, in its own session, as the link makes it."""
    printer = db.scalar(select(Printer)) or Printer(
        name="P1S", serial="01P00A000000001", host="192.168.1.40"
    )
    db.add(printer)
    tray = TrayReport(0, 0, TRAY_UID, "GFA00", "PLA", "PLA Basic", BLACK_PLA, pct)
    ingest(db, printer, [tray], T0)
    db.commit()


def test_an_ams_report_of_more_grams_queues_a_waiting_request(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, db: Session
) -> None:
    tag = SyntheticTag(color_rgba=BLACK_PLA, tray_uid=bytes.fromhex(TRAY_UID))
    pla = scan(client, token, tag, "received")["product"]["id"]
    _ams_reports(db, 20)
    waiting = _waiting(sam, frank, pla, 500)
    assert _short(waiting) == 300

    _ams_reports(db, 60)

    _moved_automatically(frank, waiting["id"])


def test_linking_a_product_to_a_catalog_color_queues_a_request_waiting_for_that_color(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _approved(sam, frank, {"catalog_color": JADE_WHITE}, 400)
    assert (waiting["status"], _short(waiting)) == ("waiting_on_filament", 400)

    response = frank.patch(
        f"/api/v1/products/{pla}", json={"catalog_color": JADE_WHITE}, headers=CSRF
    )
    assert response.status_code == 200, response.text

    _moved_automatically(frank, waiting["id"])


def _black_pla() -> SyntheticTag:
    """A new spool's tag, of the product `stock` makes for Black PLA."""
    return SyntheticTag(
        color_rgba=BLACK_PLA,
        filament_type="PLA",
        detailed_filament_type="PLA",
        material_id="GFPLA",
        variant_id="PLA-00",
    )


def _undo(client: TestClient, token: str, event_id: str) -> None:
    response = client.post(f"/api/v1/events/{event_id}/revert", headers=bearer(token))
    assert response.status_code == 200, response.text


def test_undoing_an_empty_queues_a_waiting_request(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    tag = _black_pla()
    scan(client, token, tag, "received")
    emptied = scan(client, token, tag, "empty")
    waiting = _waiting(sam, frank, pla, 1500)

    _undo(client, token, emptied["event_id"])

    _moved_automatically(frank, waiting["id"])


def test_cancelling_a_request_gives_its_grams_to_a_waiting_one(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    queued = _approved(sam, frank, {"product_id": pla}, 700)
    waiting = _waiting(sam, frank, pla, 600)

    response = sam.post(
        f"{REQUESTS}/{queued['id']}/moves",
        json={"from_status": "queued", "to_status": "cancelled", "note": ""},
        headers=CSRF,
    )
    assert response.status_code == 200, response.text

    _moved_automatically(frank, waiting["id"])


def test_a_request_approved_before_grams_were_asked_is_left_approved(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    created = submitted(sam, choices=[{"product_id": pla, "note": ""}])
    put_in(frank, created["id"], "approved")

    stock(client, token, BLACK_PLA, "PLA", "received")

    assert _read(frank, created["id"])["status"] == "approved"


# --- Order ------------------------------------------------------------------------------------


def test_the_first_request_in_active_tab_order_gets_a_new_spool_first(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    older = _waiting(sam, frank, pla, 1500)
    urgent = _waiting(sam, frank, pla, 600, priority="urgent")

    stock(client, token, BLACK_PLA, "PLA", "received")

    _moved_automatically(frank, urgent["id"])
    read = _read(frank, older["id"])
    assert (read["status"], _short(read)) == ("waiting_on_filament", 100)


# --- Spools gone ------------------------------------------------------------------------------


def _queued_on_one_spool(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> tuple[SyntheticTag, dict[str, Any], dict[str, Any]]:
    """A spool's tag, the scan that received it, and a request Queued on it."""
    tag = _black_pla()
    received = scan(client, token, tag, "received")
    created = _approved(sam, frank, {"product_id": received["product"]["id"]}, 400)
    assert created["status"] == "queued"
    return tag, received, created


def test_emptying_a_held_spool_leaves_a_queued_request_queued_and_short(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    tag, _, queued = _queued_on_one_spool(client, token, sam, frank)

    scan(client, token, tag, "empty")

    read = _read(frank, queued["id"])
    assert (read["status"], _short(read), _holds(read)) == ("queued", 400, [])


def test_undoing_a_held_spools_received_leaves_a_queued_request_queued_and_short(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    _, received, queued = _queued_on_one_spool(client, token, sam, frank)

    _undo(client, token, received["event_id"])

    read = _read(frank, queued["id"])
    assert (read["status"], _short(read), _holds(read)) == ("queued", 400, [])


# --- Queued and Printing ----------------------------------------------------------------------


def test_an_admin_queues_a_short_waiting_request_by_hand_and_it_stays_short(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _waiting(sam, frank, pla, 1500)

    response = _move(frank, waiting["id"], "waiting_on_filament", "queued")

    assert response.status_code == 200, response.text
    read = response.json()
    assert (read["status"], _short(read)) == ("queued", 500)
    assert read["history"][0]["username"] == "frank"


def test_a_printing_request_never_shows_a_shortfall(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    tag, _, queued = _queued_on_one_spool(client, token, sam, frank)
    assert _move(frank, queued["id"], "queued", "printing").status_code == 200

    scan(client, token, tag, "empty")

    read = _read(frank, queued["id"])
    assert (read["status"], _short(read)) == ("printing", None)
