"""Moving a print request through its request statuses: Approve and Reject."""

from typing import Any

import pytest
from api_helpers import CSRF, admin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from request_helpers import REQUESTS, edit, person, submitted
from sqlalchemy.orm import Session

from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import RequestStatus, Role


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


def test_an_admin_approves_a_submitted_request(sam: TestClient, frank: TestClient) -> None:
    created = submitted(sam)

    response = move(frank, created["id"], "submitted", "approved")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert _read(sam, created["id"])["status"] == "approved"


def test_an_approval_writes_a_history_entry_with_its_optional_note(
    sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)

    move(frank, created["id"], "submitted", "approved", "  Next week, probably.  ")

    entry = _read(sam, created["id"])["history"][0]
    assert entry["at"]
    assert (
        entry["kind"],
        entry["username"],
        entry["from_value"],
        entry["to_value"],
        entry["note"],
    ) == ("status_changed", "frank", "submitted", "approved", "Next week, probably.")


def test_an_approval_needs_no_note(sam: TestClient, frank: TestClient) -> None:
    created = submitted(sam)

    move(frank, created["id"], "submitted", "approved", "   ")

    assert _read(sam, created["id"])["history"][0]["note"] is None


def test_an_admin_rejects_a_submitted_request_with_a_reason(
    sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)

    response = move(frank, created["id"], "submitted", "rejected", "We have no clear PETG.")

    assert response.status_code == 200, response.text
    read = _read(sam, created["id"])
    assert read["status"] == "rejected"
    entry = read["history"][0]
    assert (entry["from_value"], entry["to_value"], entry["note"]) == (
        "submitted",
        "rejected",
        "We have no clear PETG.",
    )


@pytest.mark.parametrize("reason", ["", "   \n\t "])
def test_rejecting_without_a_reason_is_refused(
    sam: TestClient, frank: TestClient, reason: str
) -> None:
    created = submitted(sam)

    response = move(frank, created["id"], "submitted", "rejected", reason)

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {"note": "Give a reason."}
    assert _read(sam, created["id"])["status"] == "submitted"


def test_a_note_is_at_most_500_characters_once_trimmed(sam: TestClient, frank: TestClient) -> None:
    long, longest = submitted(sam), submitted(sam)

    refused = move(frank, long["id"], "submitted", "approved", "x" * 501)
    kept = move(frank, longest["id"], "submitted", "rejected", f"  {'x' * 500}  ")

    assert refused.status_code == 422
    assert "500" in refused.json()["detail"]["problems"]["note"]
    assert kept.status_code == 200
    assert _read(sam, longest["id"])["history"][0]["note"] == "x" * 500


def test_a_move_from_a_status_the_request_has_left_is_refused(
    sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    move(frank, created["id"], "submitted", "rejected", "No.")

    response = move(frank, created["id"], "submitted", "approved")

    assert response.status_code == 409
    assert response.json()["detail"] == "This request has changed. Reload to see it."
    assert _read(sam, created["id"])["status"] == "rejected"


ALLOWED = {("submitted", "approved"), ("submitted", "rejected")}
OTHER_PAIRS = [
    (a.value, b.value)
    for a in RequestStatus
    for b in RequestStatus
    if (a.value, b.value) not in ALLOWED
]


@pytest.mark.parametrize(("from_status", "to_status"), OTHER_PAIRS)
def test_every_other_move_is_refused(
    sam: TestClient, frank: TestClient, db: Session, from_status: str, to_status: str
) -> None:
    created = submitted(sam)
    db.get(PrintRequest, created["id"]).status = RequestStatus(from_status)
    db.commit()

    response = move(frank, created["id"], from_status, to_status, "Because.")

    assert response.status_code == 403
    assert _read(sam, created["id"])["status"] == from_status


def test_only_an_admin_approves_or_rejects(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam)
    dana = person(app, "dana", Role.EDITOR, requester=True)
    maya = person(app, "maya")
    viewer = person(app, "vic", requester=False)

    for to_status in ("approved", "rejected"):
        assert move(dana, created["id"], "submitted", to_status, "x").status_code == 403
        assert move(sam, created["id"], "submitted", to_status, "x").status_code == 403
        assert move(maya, created["id"], "submitted", to_status, "x").status_code == 404
        assert move(viewer, created["id"], "submitted", to_status, "x").status_code == 403
    assert _read(sam, created["id"])["status"] == "submitted"


def test_an_admin_who_asked_for_a_request_still_approves_it(
    app: FastAPI, client: TestClient
) -> None:
    ada = person(app, "ada", Role.ADMIN, requester=True)
    created = submitted(ada)

    assert _read(ada, created["id"])["moves"] == [
        {"to_status": "approved", "reason_required": False},
        {"to_status": "rejected", "reason_required": True},
    ]
    assert move(ada, created["id"], "submitted", "approved").status_code == 200


def test_the_detail_lists_the_moves_the_caller_may_make(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    dana = person(app, "dana", Role.EDITOR)

    assert _read(frank, created["id"])["moves"] == [
        {"to_status": "approved", "reason_required": False},
        {"to_status": "rejected", "reason_required": True},
    ]
    assert _read(dana, created["id"])["moves"] == []
    assert _read(sam, created["id"])["moves"] == []
    # Nothing more to do once it is approved, until the next moves are added.
    approved = move(frank, created["id"], "submitted", "approved").json()
    assert approved["moves"] == []


def test_an_admin_machine_token_moves_a_request_as_no_one(
    client: TestClient, sam: TestClient
) -> None:
    created = submitted(sam)

    response = client.post(
        f"{REQUESTS}/{created['id']}/moves",
        json={"from_status": "submitted", "to_status": "approved"},
        headers=admin(),
    )

    assert response.status_code == 200
    assert _read(sam, created["id"])["history"][0]["username"] is None


# --- Editing and priority once it moves ----------------------------------------------------


def test_an_approved_request_can_no_longer_be_edited(sam: TestClient, frank: TestClient) -> None:
    created = submitted(sam)
    move(frank, created["id"], "submitted", "approved")

    response = edit(sam, created["id"], title="Changed")

    assert response.status_code == 403
    assert _read(sam, created["id"])["can_edit"] is False


def _priority(user: TestClient, request_id: int, priority: str) -> Response:
    return user.post(f"{REQUESTS}/{request_id}/priority", json={"priority": priority}, headers=CSRF)


def test_priority_changes_while_the_request_is_open(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    move(frank, created["id"], "submitted", "approved")
    dana = person(app, "dana", Role.EDITOR)

    response = _priority(dana, created["id"], "urgent")

    assert response.status_code == 200
    assert response.json()["priority"] == "urgent"
    assert response.json()["can_change_priority"] is True


def test_a_closed_requests_priority_stays_as_it_was(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    move(frank, created["id"], "submitted", "rejected", "No.")
    dana = person(app, "dana", Role.EDITOR)

    response = _priority(dana, created["id"], "urgent")

    assert response.status_code == 403
    read = _read(dana, created["id"])
    assert (read["priority"], read["can_change_priority"]) == ("normal", False)
