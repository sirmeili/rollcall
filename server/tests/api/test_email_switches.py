"""The Account email switches: "Email me when my requests change" for every user, and "Email
me when a request is submitted" for Admins. Both are on by default, and Account says when
email isn't set up on this server."""

from api_helpers import CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import Role

ACCOUNT = "/api/v1/auth/me"


def test_both_switches_are_on_by_default(app: FastAPI, client: TestClient) -> None:
    me = signed_in(app, Role.VIEWER).get(ACCOUNT).json()

    assert me["email_on_request_change"] is True
    assert me["email_on_new_request"] is True


def test_a_user_turns_their_switches_off_and_on(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.ADMIN)

    off = user.patch(
        ACCOUNT,
        json={"email_on_request_change": False, "email_on_new_request": False},
        headers=CSRF,
    )

    assert off.status_code == 200
    assert (off.json()["email_on_request_change"], off.json()["email_on_new_request"]) == (
        False,
        False,
    )
    back = user.patch(ACCOUNT, json={"email_on_new_request": True}, headers=CSRF).json()
    assert (back["email_on_request_change"], back["email_on_new_request"]) == (False, True)


def test_changing_a_switch_keeps_the_address(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    user.patch(ACCOUNT, json={"email": "sam@example.com"}, headers=CSRF)

    me = user.patch(ACCOUNT, json={"email_on_request_change": False}, headers=CSRF).json()

    assert me["email"] == "sam@example.com"


def test_account_says_whether_email_is_set_up(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    assert user.get(ACCOUNT).json()["email_set_up"] is False

    values = {"smtp_host": "smtp.example.com"}
    client.put("/api/v1/settings/email", json={"values": values}, headers=admin())

    assert user.get(ACCOUNT).json()["email_set_up"] is True


def test_an_admin_cant_change_someone_elses_switches_on_users(
    app: FastAPI, client: TestClient
) -> None:
    user = signed_in(app, Role.VIEWER)
    user_id = user.get(ACCOUNT).json()["id"]

    response = client.patch(
        f"/api/v1/users/{user_id}", json={"email_on_request_change": False}, headers=admin()
    )

    assert response.status_code == 422
    assert user.get(ACCOUNT).json()["email_on_request_change"] is True
