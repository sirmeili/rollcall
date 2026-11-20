"""Moving an approved print request along by hand: Queued or Waiting on Filament, Printing,
Done or Failed, Reprint, and Picked Up."""

from typing import Any

import pytest
from api_helpers import CSRF, admin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from request_helpers import REQUESTS, person, submitted

from filament_tracker.domain.enums import Role

# The moves from Submitted that reach each status, by hand, one way.
ROUTE = {
    "approved": ["approved"],
    "waiting_on_filament": ["approved", "waiting_on_filament"],
    "queued": ["approved", "queued"],
    "printing": ["approved", "queued", "printing"],
    "done": ["approved", "queued", "printing", "done"],
    "failed": ["approved", "queued", "printing", "failed"],
}

ADMIN_MOVES = [
    ("approved", "queued"),
    ("approved", "waiting_on_filament"),
    ("waiting_on_filament", "queued"),
    ("queued", "printing"),
    ("printing", "done"),
    ("printing", "failed"),
    ("failed", "queued"),
]


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def move(
    user: TestClient, request_id: int, from_status: str, to_status: str, note: str = ""
) -> Response:
    return user.post(
        f"{REQUESTS}/{request_id}/moves",
        json={"from_status": from_status, "to_status": to_status, "note": note},
        headers=CSRF,
    )


def _read(user: TestClient, request_id: int) -> dict[str, Any]:
    return user.get(f"{REQUESTS}/{request_id}").json()


def _moved_to(admin_user: TestClient, request_id: int, status: str) -> None:
    """Move a Submitted request to `status` by its route."""
    at = "submitted"
    for to_status in ROUTE[status]:
        response = move(admin_user, request_id, at, to_status)
        assert response.status_code == 200, response.text
        at = to_status


def _in(sam: TestClient, frank: TestClient, status: str) -> int:
    """A request of sam's, moved to `status`."""
    created = submitted(sam)
    _moved_to(frank, created["id"], status)
    return created["id"]


@pytest.mark.parametrize(("from_status", "to_status"), ADMIN_MOVES)
def test_an_admin_moves_a_request_along_with_an_optional_note(
    sam: TestClient, frank: TestClient, from_status: str, to_status: str
) -> None:
    request_id = _in(sam, frank, from_status)

    response = move(frank, request_id, from_status, to_status, "  On the A1.  ")

    assert response.status_code == 200, response.text
    read = _read(sam, request_id)
    assert read["status"] == to_status
    entry = read["history"][0]
    assert entry["at"]
    assert (
        entry["kind"],
        entry["username"],
        entry["from_value"],
        entry["to_value"],
        entry["note"],
    ) == ("status_changed", "frank", from_status, to_status, "On the A1.")


@pytest.mark.parametrize(("from_status", "to_status"), ADMIN_MOVES)
def test_a_move_along_needs_no_note(
    sam: TestClient, frank: TestClient, from_status: str, to_status: str
) -> None:
    request_id = _in(sam, frank, from_status)

    assert move(frank, request_id, from_status, to_status).status_code == 200
    assert _read(sam, request_id)["history"][0]["note"] is None


@pytest.mark.parametrize(("from_status", "to_status"), ADMIN_MOVES)
def test_only_an_admin_moves_a_request_along(
    app: FastAPI, sam: TestClient, frank: TestClient, from_status: str, to_status: str
) -> None:
    request_id = _in(sam, frank, from_status)
    dana = person(app, "dana", Role.EDITOR, requester=True)
    maya = person(app, "maya")
    viewer = person(app, "vic", requester=False)

    assert move(dana, request_id, from_status, to_status).status_code == 403
    assert move(sam, request_id, from_status, to_status).status_code == 403
    assert move(maya, request_id, from_status, to_status).status_code == 404
    assert move(viewer, request_id, from_status, to_status).status_code == 403
    assert _read(sam, request_id)["status"] == from_status


def test_the_requester_marks_a_done_request_picked_up(sam: TestClient, frank: TestClient) -> None:
    request_id = _in(sam, frank, "done")

    response = move(sam, request_id, "done", "picked_up", "Thanks!")

    assert response.status_code == 200, response.text
    entry = _read(sam, request_id)["history"][0]
    assert (entry["username"], entry["from_value"], entry["to_value"], entry["note"]) == (
        "sam",
        "done",
        "picked_up",
        "Thanks!",
    )
    assert response.json()["status"] == "picked_up"


def test_a_former_requester_still_marks_their_request_picked_up(
    client: TestClient, sam: TestClient, frank: TestClient
) -> None:
    request_id = _in(sam, frank, "done")
    client.patch("/api/v1/users/1", json={"requester": False}, headers=admin())

    assert _read(sam, request_id)["moves"] == [
        {"to_status": "picked_up", "reason_required": False, "photos": False}
    ]
    assert move(sam, request_id, "done", "picked_up").status_code == 200


def test_an_admin_marks_a_done_request_picked_up(sam: TestClient, frank: TestClient) -> None:
    request_id = _in(sam, frank, "done")

    assert move(frank, request_id, "done", "picked_up").status_code == 200
    entry = _read(sam, request_id)["history"][0]
    assert (entry["username"], entry["to_value"], entry["note"]) == ("frank", "picked_up", None)


def test_no_one_else_marks_a_request_picked_up(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    request_id = _in(sam, frank, "done")
    dana = person(app, "dana", Role.EDITOR, requester=True)
    maya = person(app, "maya")
    viewer = person(app, "vic", requester=False)

    assert move(dana, request_id, "done", "picked_up").status_code == 403
    assert move(maya, request_id, "done", "picked_up").status_code == 404
    assert move(viewer, request_id, "done", "picked_up").status_code == 403
    assert _read(sam, request_id)["status"] == "done"


# --- Reprints and attempts -------------------------------------------------------------------


def test_a_new_request_is_its_first_attempt(sam: TestClient) -> None:
    created = submitted(sam)

    assert created["attempt"] == 1


def test_a_reprint_keeps_the_request_and_counts_another_attempt(
    sam: TestClient, frank: TestClient
) -> None:
    request_id = _in(sam, frank, "failed")
    assert _read(sam, request_id)["attempt"] == 1

    response = move(frank, request_id, "failed", "queued", "Bed adhesion.")

    assert response.status_code == 200
    read = response.json()
    assert (read["id"], read["status"], read["attempt"]) == (request_id, "queued", 2)
    entry = read["history"][0]
    assert (entry["kind"], entry["from_value"], entry["to_value"], entry["note"]) == (
        "status_changed",
        "failed",
        "queued",
        "Bed adhesion.",
    )


def test_two_reprints_make_attempt_three(sam: TestClient, frank: TestClient) -> None:
    request_id = _in(sam, frank, "failed")
    move(frank, request_id, "failed", "queued")
    for to_status in ("printing", "failed", "queued"):
        assert _read(sam, request_id)["attempt"] == 2
        at = _read(sam, request_id)["status"]
        assert move(frank, request_id, at, to_status).status_code == 200

    assert _read(sam, request_id)["attempt"] == 3


def test_queueing_an_approved_request_is_not_a_reprint(sam: TestClient, frank: TestClient) -> None:
    request_id = _in(sam, frank, "approved")
    move(frank, request_id, "approved", "waiting_on_filament")
    move(frank, request_id, "waiting_on_filament", "queued")

    assert _read(sam, request_id)["attempt"] == 1


# --- The moves offered ------------------------------------------------------------------------

CANCEL = {"to_status": "cancelled", "reason_required": True, "photos": False}
ADMIN_OFFERS = {
    "approved": ["queued", "waiting_on_filament"],
    "waiting_on_filament": ["queued"],
    "queued": ["printing"],
    "printing": ["done", "failed"],
    "done": ["picked_up"],
    "failed": ["queued"],
}
CANCELLABLE = {"approved", "waiting_on_filament", "queued", "failed"}


@pytest.mark.parametrize(("status", "offered"), ADMIN_OFFERS.items())
def test_the_detail_offers_an_admin_the_next_steps_main_one_first(
    sam: TestClient, frank: TestClient, status: str, offered: list[str]
) -> None:
    request_id = _in(sam, frank, status)

    moves = _read(frank, request_id)["moves"]

    steps = [{"to_status": to, "reason_required": False, "photos": to == "done"} for to in offered]
    assert moves == steps + ([CANCEL] if status in CANCELLABLE else [])


@pytest.mark.parametrize("status", ["approved", "waiting_on_filament", "queued", "printing"])
def test_the_detail_offers_the_requester_only_cancel_before_done(
    sam: TestClient, frank: TestClient, status: str
) -> None:
    request_id = _in(sam, frank, status)

    cancel = [{"to_status": "cancelled", "reason_required": False, "photos": False}]
    assert _read(sam, request_id)["moves"] == ([] if status == "printing" else cancel)


def test_the_detail_offers_the_requester_picked_up_once_done(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    request_id = _in(sam, frank, "done")
    dana = person(app, "dana", Role.EDITOR)

    assert _read(sam, request_id)["moves"] == [
        {"to_status": "picked_up", "reason_required": False, "photos": False}
    ]
    assert _read(dana, request_id)["moves"] == []


def test_a_picked_up_request_has_no_moves_left(sam: TestClient, frank: TestClient) -> None:
    request_id = _in(sam, frank, "done")
    move(sam, request_id, "done", "picked_up")

    assert _read(frank, request_id)["moves"] == []
    assert _read(sam, request_id)["moves"] == []
