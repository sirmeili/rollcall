"""The push configuration a signed-in user's phone registers with: the server's VAPID public
key, made on first start and kept."""

from api_helpers import (
    ADMIN_TOKEN,
    BASE_URL,
    CSRF,
    INTERNET_CLIENT,
    LAN_CLIENT,
    bearer,
    browser,
    signed_in,
)
from fake_push_outbox import FakePushOutbox, unb64url
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import CONFIG

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app


def test_a_signed_in_user_gets_the_vapid_public_key(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)

    response = user.get(CONFIG)

    assert response.status_code == 200
    key = unb64url(response.json()["vapid_public_key"])
    # An uncompressed P-256 point.
    assert len(key) == 65 and key[0] == 4
    assert response.headers["cache-control"] == "no-store"


def test_it_answers_from_outside_the_lan(app: FastAPI, client: TestClient) -> None:
    away = signed_in(app, Role.VIEWER, INTERNET_CLIENT)

    assert away.get(CONFIG).status_code == 200


def test_the_key_pair_is_made_once_and_kept(db_url: str, pushes: FakePushOutbox) -> None:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    keys = []
    for _ in range(2):
        app = create_app(settings, push_transport=pushes)
        with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT):
            keys.append(signed_in(app, Role.VIEWER, username=f"user{len(keys)}").get(CONFIG).json())

    assert keys[0] == keys[1]


def test_a_device_token_or_no_sign_in_is_refused(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    token = user.post("/api/v1/devices/mine", json={"name": "Pixel"}, headers=CSRF).json()["token"]

    assert browser(app).get(CONFIG).status_code == 401
    assert browser(app).get(CONFIG, headers=bearer(token)).status_code == 403
