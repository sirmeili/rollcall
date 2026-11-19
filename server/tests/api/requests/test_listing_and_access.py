"""The Requests list and who may see which request."""

from datetime import date, timedelta

from api_helpers import admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, person, submitted

from filament_tracker.domain.enums import Role


def _soon(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_a_requester_lists_only_their_own_requests(app: FastAPI, client: TestClient) -> None:
    sam, maya = person(app, "sam"), person(app, "maya")
    mine = submitted(sam, title="Sam's clips")
    submitted(maya, title="Maya's rack")

    rows = sam.get(REQUESTS).json()

    assert [r["id"] for r in rows] == [mine["id"]]


def test_each_row_has_what_the_list_shows(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")
    created = submitted(sam, quantity=2, needed_by=_soon(3), priority="urgent")

    [row] = sam.get(REQUESTS).json()

    assert row == {
        "id": created["id"],
        "title": "Lithophane lamp shade",
        "quantity": 2,
        "needed_by": _soon(3),
        "priority": "urgent",
        "status": "submitted",
        "requester": {"id": 1, "username": "sam"},
        "model": "link",
        "choices": [{"name": "Jade White PLA Basic", "hexes": ["FFFFFF"]}],
        "created_at": created["created_at"],
    }


def test_the_row_says_what_the_model_is(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")
    submitted(sam, link=None, notes="On the USB stick")

    assert sam.get(REQUESTS).json()[0]["model"] == "notes"


def test_editors_and_admins_see_every_request_most_pressing_first(
    app: FastAPI, client: TestClient
) -> None:
    sam, maya = person(app, "sam"), person(app, "maya")
    ids = {
        "normal-late": submitted(sam, needed_by=_soon(20))["id"],
        "no-rush": submitted(maya, priority="no_rush", needed_by=_soon(1))["id"],
        "normal-undated-old": submitted(maya)["id"],
        "urgent-undated": submitted(sam, priority="urgent")["id"],
        "normal-soon": submitted(maya, needed_by=_soon(2))["id"],
        "normal-undated-new": submitted(sam)["id"],
        "urgent-dated": submitted(maya, priority="urgent", needed_by=_soon(30))["id"],
    }
    order = [
        "urgent-dated",
        "urgent-undated",
        "normal-soon",
        "normal-late",
        "normal-undated-old",
        "normal-undated-new",
        "no-rush",
    ]

    for role in (Role.EDITOR, Role.ADMIN):
        rows = signed_in(app, role).get(REQUESTS).json()
        assert [r["id"] for r in rows] == [ids[name] for name in order]
    assert {r["requester"]["username"] for r in rows} == {"sam", "maya"}


def test_a_requester_cannot_open_another_users_request(app: FastAPI, client: TestClient) -> None:
    sam, maya = person(app, "sam"), person(app, "maya")
    theirs = submitted(maya)

    assert sam.get(f"{REQUESTS}/{theirs['id']}").status_code == 404
    assert sam.get(f"{REQUESTS}/9999").status_code == 404


def test_editors_open_any_request(app: FastAPI, client: TestClient) -> None:
    theirs = submitted(person(app, "maya"))

    editor = signed_in(app, Role.EDITOR)

    assert editor.get(f"{REQUESTS}/{theirs['id']}").status_code == 200
    assert client.get(f"{REQUESTS}/{theirs['id']}", headers=admin()).status_code == 200


def test_a_viewer_who_never_was_a_requester_is_refused(app: FastAPI, client: TestClient) -> None:
    theirs = submitted(person(app, "maya"))
    viewer = person(app, "theo", requester=False)

    assert viewer.get(REQUESTS).status_code == 403
    assert viewer.get(f"{REQUESTS}/{theirs['id']}").status_code == 403


def test_a_former_requester_still_reads_their_own_requests(
    app: FastAPI, client: TestClient
) -> None:
    sam = person(app, "sam")
    mine = submitted(sam)
    client.patch("/api/v1/users/1", json={"requester": False}, headers=admin())

    assert [r["id"] for r in sam.get(REQUESTS).json()] == [mine["id"]]
    read = sam.get(f"{REQUESTS}/{mine['id']}").json()
    assert read["title"] == "Lithophane lamp shade"
    assert read["can_edit"] is False
    me = sam.get("/api/v1/auth/me").json()
    assert (me["requester"], me["has_requests"]) == (False, True)


def test_the_count_of_submitted_requests_is_for_editors(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")
    submitted(sam)
    submitted(sam)

    assert signed_in(app, Role.EDITOR).get(f"{REQUESTS}/count").json() == {"submitted": 2}
    assert sam.get(f"{REQUESTS}/count").status_code == 403
