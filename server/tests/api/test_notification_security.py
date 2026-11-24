"""Security suite: a user's notification settings are read and changed only by that user, in a
signed-in browser. Nobody else, an Admin or a token included, decides what they're told, and
nobody chooses a kind outside their role. A notification email's link comes from PUBLIC_URL,
never from the incoming request's Host header."""

import sys
from pathlib import Path

import pytest
from api_helpers import ADMIN_TOKEN, CSRF, admin, signed_in
from fake_outbox import FakeOutbox, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_shopping_list_by_hand import _black

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

# The request email tests' helpers: email set up, choosing a kind, and what was sent.
sys.path.insert(0, str(Path(__file__).parent / "requests"))

from email_helpers import PUBLIC_URL, email_on, notify, sent  # noqa: E402

ACCOUNT = "/api/v1/auth/me"
TURN_OFF = {"notifications": [{"kind": "new_request", "channel": "email", "on": False}]}


@pytest.fixture
def outbox() -> FakeOutbox:
    """Where the server's emails go instead of a mail server."""
    return FakeOutbox()


@pytest.fixture
def app(db_url: str, outbox: FakeOutbox) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    return create_app(settings, mail_transport=outbox)


def _new_request(user: TestClient) -> dict[str, object]:
    return user.get(ACCOUNT).json()["notifications"][0]


def _setting(kind: str, on: bool, *, default: bool = True) -> dict[str, object]:
    return {"kind": kind, "channel": "email", "on": on, "default": default}


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


def test_a_kind_outside_the_role_is_refused_and_nothing_changes(
    app: FastAPI, client: TestClient
) -> None:
    viewer = signed_in(app, Role.VIEWER, requester=True)

    response = viewer.patch(
        ACCOUNT,
        json={
            "notifications": [
                {"kind": "new_photo", "channel": "email", "on": False},
                {"kind": "new_request", "channel": "email", "on": True},
            ]
        },
        headers=CSRF,
    )

    assert response.status_code == 403
    settings = viewer.get(ACCOUNT).json()["notifications"]
    assert [s for s in settings if s["channel"] == "email"] == [
        _setting("request_update", True),
        _setting("new_photo", True),
        _setting("low_stock", False),
        _setting("nearly_out", False),
    ]


def test_links_ignore_the_requests_host_header(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    boss = signed_in(app, Role.ADMIN, username="boss")
    boss.patch(ACCOUNT, json={"email": "boss@example.com"}, headers=CSRF)
    notify(boss, "suggestion", True)
    vic = signed_in(app, Role.VIEWER, username="vic")
    black = _black(db)

    response = vic.post(
        "/api/v1/shopping-list/suggestions",
        json={"product_id": black.id, "spools": 1},
        headers={**CSRF, "Host": "evil.example.net"},
    )

    assert response.status_code == 200
    [message] = sent(app, outbox)
    assert "evil.example.net" not in text_of(message)
    assert f"{PUBLIC_URL}/shopping-list" in text_of(message)
