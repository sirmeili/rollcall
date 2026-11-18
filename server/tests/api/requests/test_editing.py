"""Editing a request while it is Submitted, and changing its priority."""

from datetime import date, timedelta

import pytest
from api_helpers import CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, changed_export, gz, ok, refresh
from request_helpers import BLACK, JADE_WHITE, REQUESTS, edit, person, submitted

from filament_tracker.domain.enums import Role


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


def _history(user: TestClient, request_id: int) -> list[dict]:
    return user.get(f"{REQUESTS}/{request_id}").json()["history"]


def test_the_requester_edits_any_field_and_the_history_lists_what_changed(
    sam: TestClient,
) -> None:
    created = submitted(sam)
    needed = (date.today() + timedelta(days=5)).isoformat()

    response = edit(
        sam,
        created["id"],
        title="Lamp shade, v2",
        needed_by=needed,
        notes="White only, please.",
        choices=[{"catalog_color": JADE_WHITE, "note": ""}, {"catalog_color": BLACK}],
    )

    assert response.status_code == 200, response.text
    read = response.json()
    assert (read["title"], read["needed_by"], read["notes"]) == (
        "Lamp shade, v2",
        needed,
        "White only, please.",
    )
    assert len(read["choices"]) == 2
    latest = read["history"][0]
    assert (latest["kind"], latest["username"]) == ("edited", "sam")
    assert latest["fields"] == ["title", "needed_by", "notes", "filament"]
    assert [h["kind"] for h in read["history"]] == ["edited", "submitted"]


def test_reordering_or_changing_a_note_is_a_filament_change(sam: TestClient) -> None:
    two = [{"catalog_color": JADE_WHITE}, {"catalog_color": BLACK}]
    created = submitted(sam, choices=two)

    swapped = edit(sam, created["id"], choices=list(reversed(two))).json()

    assert swapped["history"][0]["fields"] == ["filament"]
    assert [c["catalog_color"] for c in swapped["choices"]] == [BLACK, JADE_WHITE]


def test_an_edit_that_changes_nothing_writes_no_history(sam: TestClient) -> None:
    created = submitted(sam)

    assert edit(sam, created["id"]).status_code == 200

    assert [h["kind"] for h in _history(sam, created["id"])] == ["submitted"]


def test_edits_follow_the_rules_of_a_new_request(sam: TestClient) -> None:
    created = submitted(sam)

    response = edit(sam, created["id"], title="", link=None, notes="")

    assert response.status_code == 422
    assert set(response.json()["detail"]["problems"]) == {"title", "notes"}


def test_a_past_needed_by_date_is_refused_when_it_is_changed(sam: TestClient) -> None:
    created = submitted(sam)
    past = (date.today() - timedelta(days=2)).isoformat()

    problems = edit(sam, created["id"], needed_by=past).json()["detail"]["problems"]

    assert "needed_by" in problems


def test_only_the_requester_edits(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam)
    maya = person(app, "maya")
    editor = person(app, "dana", Role.EDITOR, requester=True)

    assert edit(maya, created["id"]).status_code == 404
    assert edit(editor, created["id"]).status_code == 403


def test_a_former_requester_cannot_edit(client: TestClient, sam: TestClient) -> None:
    created = submitted(sam)
    client.patch("/api/v1/users/1", json={"requester": False}, headers=admin())

    response = edit(sam, created["id"], title="Changed")

    assert response.status_code == 403
    assert "no longer" in response.json()["detail"]


def test_a_chosen_catalog_color_that_leaves_the_catalog_is_kept(
    sam: TestClient, client: TestClient, ofdb: FakeSource
) -> None:
    created = submitted(sam)
    ofdb.serve(ok(gz(changed_export()), etag='"v2-etag"'))
    refresh(client)

    [choice] = sam.get(f"{REQUESTS}/{created['id']}").json()["choices"]

    assert (choice["catalog_color"], choice["in_catalog"]) == (JADE_WHITE, False)
    assert choice["name"] == "Jade White PLA Basic"
    assert choice["hexes"] == ["FFFFFF"]
    # Editing other fields keeps it.
    assert edit(sam, created["id"], title="New title").status_code == 200


# --- Priority ------------------------------------------------------------------------------


def test_editors_and_admins_change_any_requests_priority(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam)
    editor = signed_in(app, Role.EDITOR, username="dana")

    response = editor.post(
        f"{REQUESTS}/{created['id']}/priority", json={"priority": "urgent"}, headers=CSRF
    )

    assert response.status_code == 200
    assert response.json()["priority"] == "urgent"
    entry = _history(sam, created["id"])[0]
    assert (entry["kind"], entry["username"], entry["from_value"], entry["to_value"]) == (
        "priority_changed",
        "dana",
        "normal",
        "urgent",
    )


def test_the_same_priority_again_writes_no_history(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam)
    editor = signed_in(app, Role.EDITOR)

    editor.post(f"{REQUESTS}/{created['id']}/priority", json={"priority": "normal"}, headers=CSRF)

    assert len(_history(sam, created["id"])) == 1


def test_a_requester_cannot_use_the_priority_change(sam: TestClient) -> None:
    created = submitted(sam)

    response = sam.post(
        f"{REQUESTS}/{created['id']}/priority", json={"priority": "urgent"}, headers=CSRF
    )

    assert response.status_code == 403


def test_the_detail_says_what_the_caller_may_do(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam)
    editor = signed_in(app, Role.EDITOR)

    mine = sam.get(f"{REQUESTS}/{created['id']}").json()
    theirs = editor.get(f"{REQUESTS}/{created['id']}").json()

    assert (mine["can_edit"], mine["can_change_priority"]) == (True, False)
    assert (theirs["can_edit"], theirs["can_change_priority"]) == (False, True)
