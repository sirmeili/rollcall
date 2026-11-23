"""The push configuration a signed-in user's phone registers with: the server's VAPID public
key, made on first start and kept."""

from api_helpers import (
    ADMIN_TOKEN,
    BASE_URL,
    CSRF,
    INTERNET_CLIENT,
    LAN_CLIENT,
    admin,
    bearer,
    browser,
    signed_in,
)
from fake_push_outbox import FIREBASE, FakePushOutbox, service_account, unb64url
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import CONFIG

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

SETTINGS = "/api/v1/settings/phone-notifications"


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


def test_without_firebase_the_config_names_none(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)

    assert user.get(CONFIG).json()["firebase"] is None


def test_with_firebase_set_up_the_phone_gets_its_client_settings(
    app: FastAPI, client: TestClient
) -> None:
    key = service_account().json
    values = {**FIREBASE, "firebase_service_account": key}
    assert client.put(SETTINGS, json={"values": values}, headers=admin()).status_code == 200
    user = signed_in(app, Role.VIEWER)

    response = user.get(CONFIG)

    assert response.json()["firebase"] == {
        "project_id": FIREBASE["firebase_project_id"],
        "app_id": FIREBASE["firebase_app_id"],
        "api_key": FIREBASE["firebase_api_key"],
        "sender_id": FIREBASE["firebase_sender_id"],
    }
    assert "PRIVATE KEY" not in response.text


def test_firebase_counts_as_set_up_only_with_all_five_settings(
    app: FastAPI, client: TestClient
) -> None:
    client.put(SETTINGS, json={"values": FIREBASE}, headers=admin())
    user = signed_in(app, Role.VIEWER)

    assert user.get(CONFIG).json()["firebase"] is None
