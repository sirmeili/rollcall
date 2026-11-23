"""Security suite: a user's notification settings are read and changed only by that user, in a
signed-in browser. Nobody else, an Admin or a token included, decides what they're told."""

from api_helpers import CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import Role

ACCOUNT = "/api/v1/auth/me"
TURN_OFF = {"notifications": [{"kind": "new_request", "channel": "email", "on": False}]}


def _new_request(user: TestClient) -> dict[str, object]:
    return user.get(ACCOUNT).json()["notifications"][0]


def test_changing_ones_settings_leaves_everyone_elses_alone(
    app: FastAPI, client: TestClient
) -> None:
    frank = signed_in(app, Role.ADMIN, username="frank")
    mia = signed_in(app, Role.ADMIN, username="mia")

    assert frank.patch(ACCOUNT, json=TURN_OFF, headers=CSRF).status_code == 200

    assert _new_request(frank)["on"] is False
    assert _new_request(mia) == {
        "kind": "new_request",
        "channel": "email",
        "on": True,
        "default": True,
    }


def test_an_admin_cant_change_someone_elses_settings_on_users(
    app: FastAPI, client: TestClient
) -> None:
    mia = signed_in(app, Role.ADMIN, username="mia")
    mia_id = mia.get(ACCOUNT).json()["id"]

    response = client.patch(f"/api/v1/users/{mia_id}", json=TURN_OFF, headers=admin())

    assert response.status_code == 422
    assert _new_request(mia)["on"] is True


def test_the_users_list_never_shows_anyones_settings(app: FastAPI, client: TestClient) -> None:
    signed_in(app, Role.ADMIN, username="mia")

    users = client.get("/api/v1/users", headers=admin()).json()

    assert users
    assert all("notifications" not in user for user in users)


def test_a_token_has_no_settings_to_read_or_change(app: FastAPI, client: TestClient) -> None:
    assert client.get(ACCOUNT, headers=admin()).status_code in (401, 403)
    assert client.patch(ACCOUNT, json=TURN_OFF, headers={**admin(), **CSRF}).status_code in (
        401,
        403,
    )


def test_a_change_without_the_csrf_header_is_refused(app: FastAPI, client: TestClient) -> None:
    frank = signed_in(app, Role.ADMIN, username="frank")

    assert frank.patch(ACCOUNT, json=TURN_OFF).status_code == 403
    assert _new_request(frank)["on"] is True
