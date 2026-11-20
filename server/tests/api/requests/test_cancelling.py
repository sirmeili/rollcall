"""Cancelling a print request: the requester before it prints, or an Admin with a reason."""

from typing import Any

import pytest
from api_helpers import admin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, edit, person, submitted
from sqlalchemy.orm import Session
from test_moves import move

from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import RequestStatus, Role

WAITING = ["submitted", "approved", "waiting_on_filament", "queued"]


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _read(user: TestClient, request_id: int) -> dict[str, Any]:
    return user.get(f"{REQUESTS}/{request_id}").json()


def _in(db: Session, request: dict[str, Any], status: str) -> int:
    """Put the request in `status`, as the moves before it would have."""
    db.get(PrintRequest, request["id"]).status = RequestStatus(status)
    db.commit()
    return request["id"]


@pytest.mark.parametrize("status", WAITING)
def test_the_requester_cancels_their_request_before_it_prints(
    sam: TestClient, db: Session, status: str
) -> None:
    request_id = _in(db, submitted(sam), status)

    response = move(sam, request_id, status, "cancelled", "  Found one in a shop.  ")

    assert response.status_code == 200, response.text
    read = _read(sam, request_id)
    assert read["status"] == "cancelled"
    entry = read["history"][0]
    assert (entry["username"], entry["from_value"], entry["to_value"], entry["note"]) == (
        "sam",
        status,
        "cancelled",
        "Found one in a shop.",
    )


def test_a_note_is_optional_when_the_requester_cancels(sam: TestClient) -> None:
    created = submitted(sam)

    move(sam, created["id"], "submitted", "cancelled", "   ")

    assert _read(sam, created["id"])["history"][0]["note"] is None


def test_a_former_requester_still_cancels_but_cannot_edit(
    client: TestClient, sam: TestClient
) -> None:
    created = submitted(sam)
    client.patch("/api/v1/users/1", json={"requester": False}, headers=admin())

    assert edit(sam, created["id"], title="Changed").status_code == 403
    assert move(sam, created["id"], "submitted", "cancelled").status_code == 200
    assert _read(sam, created["id"])["status"] == "cancelled"


@pytest.mark.parametrize("status", ["printing", "done", "picked_up", "failed"])
def test_the_requester_cannot_cancel_once_it_has_started_printing(
    sam: TestClient, db: Session, status: str
) -> None:
    request_id = _in(db, submitted(sam), status)

    response = move(sam, request_id, status, "cancelled")

    assert response.status_code == 403
    assert _read(sam, request_id)["status"] == status


@pytest.mark.parametrize("status", [*WAITING, "failed"])
def test_an_admin_cancels_a_request_with_a_reason(
    sam: TestClient, frank: TestClient, db: Session, status: str
) -> None:
    request_id = _in(db, submitted(sam), status)

    response = move(frank, request_id, status, "cancelled", "The printer is away for repair.")

    assert response.status_code == 200, response.text
    entry = _read(sam, request_id)["history"][0]
    assert (entry["username"], entry["from_value"], entry["to_value"], entry["note"]) == (
        "frank",
        status,
        "cancelled",
        "The printer is away for repair.",
    )


@pytest.mark.parametrize("reason", ["", "  \n "])
def test_an_admin_cancelling_someone_elses_request_gives_a_reason(
    sam: TestClient, frank: TestClient, reason: str
) -> None:
    created = submitted(sam)

    response = move(frank, created["id"], "submitted", "cancelled", reason)

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {"note": "Give a reason."}
    assert _read(sam, created["id"])["status"] == "submitted"


@pytest.mark.parametrize("status", ["submitted", "failed"])
def test_an_admin_cancelling_their_own_request_needs_no_reason(
    app: FastAPI, client: TestClient, db: Session, status: str
) -> None:
    ada = person(app, "ada", Role.ADMIN, requester=True)
    request_id = _in(db, submitted(ada), status)

    response = move(ada, request_id, status, "cancelled")

    assert response.status_code == 200, response.text
    assert _read(ada, request_id)["status"] == "cancelled"


@pytest.mark.parametrize("status", ["printing", "done", "picked_up"])
def test_no_one_cancels_a_request_once_it_has_printed_or_is_printing(
    app: FastAPI, sam: TestClient, frank: TestClient, db: Session, status: str
) -> None:
    request_id = _in(db, submitted(sam), status)

    response = move(frank, request_id, status, "cancelled", "Because.")

    assert response.status_code == 403
    assert _read(sam, request_id)["status"] == status


def test_editors_and_other_requesters_cannot_cancel(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam)
    dana = person(app, "dana", Role.EDITOR, requester=True)
    maya = person(app, "maya")

    assert move(dana, created["id"], "submitted", "cancelled", "x").status_code == 403
    assert move(maya, created["id"], "submitted", "cancelled", "x").status_code == 404
    assert _read(sam, created["id"])["status"] == "submitted"


CANCEL_FREELY = {"to_status": "cancelled", "reason_required": False}
CANCEL_WITH_REASON = {"to_status": "cancelled", "reason_required": True}


@pytest.mark.parametrize("status", WAITING)
def test_the_detail_offers_cancel_to_the_requester_and_admins_before_it_prints(
    app: FastAPI, sam: TestClient, frank: TestClient, db: Session, status: str
) -> None:
    request_id = _in(db, submitted(sam), status)
    dana = person(app, "dana", Role.EDITOR)

    assert _read(sam, request_id)["moves"] == [CANCEL_FREELY]
    assert CANCEL_WITH_REASON in _read(frank, request_id)["moves"]
    assert _read(dana, request_id)["moves"] == []


def test_the_detail_offers_an_admin_cancel_of_their_own_request_without_a_reason(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    ada = person(app, "ada", Role.ADMIN, requester=True)
    request_id = _in(db, submitted(ada), "failed")

    assert CANCEL_FREELY in _read(ada, request_id)["moves"]


@pytest.mark.parametrize("status", ["printing", "done", "picked_up", "failed"])
def test_the_detail_offers_the_requester_no_cancel_once_printing_starts(
    sam: TestClient, frank: TestClient, db: Session, status: str
) -> None:
    request_id = _in(db, submitted(sam), status)

    assert CANCEL_FREELY not in _read(sam, request_id)["moves"]
    offered = [m["to_status"] for m in _read(frank, request_id)["moves"]]
    assert ("cancelled" in offered) is (status == "failed")
