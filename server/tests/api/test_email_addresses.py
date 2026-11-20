"""Users' email addresses: optional, not verified, edited by the user on Account and by an
Admin on Users."""

import pytest
from api_helpers import CSRF, admin, make_user, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import Role

ACCOUNT = "/api/v1/auth/me"


def test_a_user_has_no_address_at_first(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)

    assert user.get(ACCOUNT).json()["email"] is None


def test_a_user_sets_their_own_address_on_account(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)

    response = user.patch(ACCOUNT, json={"email": "  sam@example.com "}, headers=CSRF)

    assert response.status_code == 200
    assert response.json()["email"] == "sam@example.com"
    assert user.get(ACCOUNT).json()["email"] == "sam@example.com"


def test_a_user_clears_their_address(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    user.patch(ACCOUNT, json={"email": "sam@example.com"}, headers=CSRF)

    for empty in ("", None):
        response = user.patch(ACCOUNT, json={"email": empty}, headers=CSRF)
        assert response.status_code == 200
        assert response.json()["email"] is None


BAD_ADDRESSES = [
    "no-at-sign.example.com",
    "two@at@example.com",
    "sam@localhost",
    "@example.com",
    "sam@",
    "sam@.com",
    "sam@example.",
    "sam smith@example.com",
    "a" * 243 + "@example.com",  # 255 characters
]


@pytest.mark.parametrize("address", BAD_ADDRESSES)
def test_an_address_needs_one_at_sign_and_a_dot_in_the_domain(
    app: FastAPI, client: TestClient, address: str
) -> None:
    user = signed_in(app, Role.VIEWER)

    response = user.patch(ACCOUNT, json={"email": address}, headers=CSRF)

    assert response.status_code == 422
    assert user.get(ACCOUNT).json()["email"] is None


def test_an_address_may_be_254_characters(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    longest = "a" * 242 + "@example.com"

    response = user.patch(ACCOUNT, json={"email": longest}, headers=CSRF)

    assert response.status_code == 200
    assert response.json()["email"] == longest


def test_account_changes_need_a_signed_in_user(client: TestClient) -> None:
    response = client.patch(ACCOUNT, json={"email": "x@example.com"}, headers=admin())

    assert response.status_code == 403


def test_an_admin_sets_any_users_address_on_users(app: FastAPI, client: TestClient) -> None:
    boss = signed_in(app, Role.ADMIN, username="boss")
    sam_id = make_user(app, "sam", Role.VIEWER)

    response = boss.patch(
        f"/api/v1/users/{sam_id}", json={"email": "sam@example.com"}, headers=CSRF
    )

    assert response.status_code == 200
    assert response.json()["email"] == "sam@example.com"
    listed = {u["username"]: u["email"] for u in boss.get("/api/v1/users").json()}
    assert listed == {"boss": None, "sam": "sam@example.com"}


def test_an_admin_clears_a_users_address(app: FastAPI, client: TestClient) -> None:
    sam_id = make_user(app, "sam", Role.VIEWER)
    client.patch(f"/api/v1/users/{sam_id}", json={"email": "sam@example.com"}, headers=admin())

    response = client.patch(f"/api/v1/users/{sam_id}", json={"email": ""}, headers=admin())

    assert response.json()["email"] is None


def test_leaving_the_address_out_keeps_it(app: FastAPI, client: TestClient) -> None:
    sam_id = make_user(app, "sam", Role.VIEWER)
    client.patch(f"/api/v1/users/{sam_id}", json={"email": "sam@example.com"}, headers=admin())

    response = client.patch(f"/api/v1/users/{sam_id}", json={"role": "editor"}, headers=admin())

    assert response.json()["email"] == "sam@example.com"


@pytest.mark.parametrize("address", BAD_ADDRESSES)
def test_users_refuses_a_bad_address(app: FastAPI, client: TestClient, address: str) -> None:
    sam_id = make_user(app, "sam", Role.VIEWER)

    response = client.patch(f"/api/v1/users/{sam_id}", json={"email": address}, headers=admin())

    assert response.status_code == 422
