"""Requester: a yes/no permission on top of a role (ADR-0017), set by Admins."""

from api_helpers import CSRF, admin, browser, login, make_user, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import Role

NEW = {"username": "nora", "password": "noras long password", "role": "viewer"}


def test_a_new_user_is_not_a_requester_unless_ticked(client: TestClient) -> None:
    plain = client.post("/api/v1/users", json=NEW, headers=admin())
    ticked = client.post(
        "/api/v1/users",
        json={**NEW, "username": "sam", "requester": True},
        headers=admin(),
    )

    assert plain.json()["requester"] is False
    assert ticked.json()["requester"] is True
    listed = {
        u["username"]: u["requester"] for u in client.get("/api/v1/users", headers=admin()).json()
    }
    assert listed == {"nora": False, "sam": True}


def test_admins_turn_requester_on_and_off(app: FastAPI, client: TestClient) -> None:
    user_id = make_user(app, "sam", Role.VIEWER)

    on = client.patch(f"/api/v1/users/{user_id}", json={"requester": True}, headers=admin())
    off = client.patch(f"/api/v1/users/{user_id}", json={"requester": False}, headers=admin())

    assert on.json()["requester"] is True
    assert off.json()["requester"] is False
    assert off.json()["role"] == "viewer"


def test_requester_goes_with_any_role(client: TestClient) -> None:
    for role in ("viewer", "editor", "admin"):
        body = {**NEW, "username": f"user-{role}", "role": role, "requester": True}
        created = client.post("/api/v1/users", json=body, headers=admin()).json()
        assert (created["role"], created["requester"]) == (role, True)


def test_changing_the_role_keeps_requester(app: FastAPI, client: TestClient) -> None:
    user_id = make_user(app, "sam", Role.VIEWER, requester=True)

    response = client.patch(f"/api/v1/users/{user_id}", json={"role": "editor"}, headers=admin())

    assert response.json()["requester"] is True


def test_requester_never_passes_a_role_check(app: FastAPI, client: TestClient) -> None:
    make_user(app, "sam", Role.VIEWER, requester=True)
    sam = browser(app)
    login(sam, "sam")

    assert sam.patch("/api/v1/products/1", json={}, headers=CSRF).status_code == 403
    assert sam.get("/api/v1/users").status_code == 403


def test_me_says_whether_the_user_is_a_requester(app: FastAPI, client: TestClient) -> None:
    make_user(app, "sam", Role.VIEWER, requester=True)
    sam = browser(app)
    login(sam, "sam")
    viewer = signed_in(app, Role.VIEWER)

    assert sam.get("/api/v1/auth/me").json()["requester"] is True
    assert viewer.get("/api/v1/auth/me").json()["requester"] is False
    assert viewer.get("/api/v1/auth/me").json()["has_requests"] is False
