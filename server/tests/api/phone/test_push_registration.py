"""A user's phone registers and removes its push endpoint with the signed-in session, from
anywhere; only for the user's own phone that isn't revoked, never with a device token alone.
Whether a phone is registered shows in whether its test notification is sent."""

import pytest
from api_helpers import (
    CSRF,
    INTERNET_CLIENT,
    admin,
    bearer,
    browser,
    login,
    make_user,
    register,
    signed_in,
)
from fake_push_outbox import FakePushOutbox, TestPhone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import endpoint_path, register_phone, set_up_phone

from filament_tracker.domain.enums import Role

ACCOUNT = "/api/v1/auth/me"


def _test(user: TestClient, device_id: str) -> object:
    return user.post(f"{endpoint_path(device_id)}/test", headers=CSRF)


def test_a_user_registers_their_phone_and_gets_a_test_notification(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    user = signed_in(app, Role.VIEWER)
    phone = TestPhone()
    device_id = set_up_phone(user)

    response = register_phone(user, device_id, phone)

    assert response.status_code == 200
    assert response.json()["device_id"] == device_id
    assert response.json()["route"] == "web_push"
    tested = _test(user, device_id)
    assert tested.json() == {"ok": True, "message": "Sent a test notification to this phone."}
    [message] = pushes.sent
    assert phone.decrypt(message) == {
        "kind": "test",
        "title": "Test notification",
        "text": "Phone notifications work on this phone.",
        "path": "/",
    }


def test_a_test_notification_is_allowed_once_every_30_seconds_per_phone(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    user = signed_in(app, Role.VIEWER)
    first, second = set_up_phone(user, "Pixel"), set_up_phone(user, "Tablet")
    for device_id in (first, second):
        register_phone(user, device_id, TestPhone())

    assert _test(user, first).json()["ok"] is True
    too_soon = _test(user, first)
    assert too_soon.status_code == 429
    assert (
        too_soon.json()["detail"] == "Wait a few seconds before sending another test notification."
    )
    # Each phone has its own limit.
    assert _test(user, second).json()["ok"] is True
    assert pushes.attempts == 2


@pytest.mark.parametrize(
    ("status", "message", "kept"),
    [
        (503, "The push service answered 503.", True),
        (None, "The push service didn't answer in time.", True),
        (410, "This phone's push endpoint is gone.", False),
    ],
)
def test_a_failed_test_notification_says_why(
    app: FastAPI,
    client: TestClient,
    pushes: FakePushOutbox,
    status: int | None,
    message: str,
    kept: bool,
) -> None:
    user = signed_in(app, Role.VIEWER)
    device_id = set_up_phone(user)
    register_phone(user, device_id, TestPhone())
    pushes.answer(status)

    assert _test(user, device_id).json() == {"ok": False, "message": message}
    assert user.get(ACCOUNT).json()["phone_registered"] is kept


def test_registering_and_removing_work_from_outside_the_lan(
    app: FastAPI, client: TestClient
) -> None:
    make_user(app, "bob", Role.VIEWER)
    home = browser(app)
    login(home, "bob")
    device_id = set_up_phone(home)
    away = browser(app, INTERNET_CLIENT)
    assert login(away, "bob").status_code == 200

    assert register_phone(away, device_id, TestPhone()).status_code == 200
    assert away.delete(endpoint_path(device_id), headers=CSRF).status_code == 204

    assert _test(away, device_id).status_code == 409


def test_a_removed_phone_gets_no_test_notification(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    device_id = set_up_phone(user)
    register_phone(user, device_id, TestPhone())

    assert user.delete(endpoint_path(device_id), headers=CSRF).status_code == 204
    # Removing again is fine.
    assert user.delete(endpoint_path(device_id), headers=CSRF).status_code == 204

    tested = _test(user, device_id)
    assert tested.status_code == 409
    assert tested.json()["detail"] == "This phone isn't registered for phone notifications."


def test_another_users_phone_is_refused(app: FastAPI, client: TestClient) -> None:
    bob = signed_in(app, Role.VIEWER, username="bob")
    mallory = signed_in(app, Role.ADMIN, username="mallory")
    bobs_phone = set_up_phone(bob)
    register_phone(bob, bobs_phone, TestPhone())

    assert register_phone(mallory, bobs_phone, TestPhone()).status_code == 404
    assert mallory.delete(endpoint_path(bobs_phone), headers=CSRF).status_code == 404
    assert _test(mallory, bobs_phone).status_code == 404
    assert _test(bob, bobs_phone).json()["ok"] is True


def test_a_shared_phone_or_an_unknown_one_is_refused(app: FastAPI, client: TestClient) -> None:
    register(client, "shared-phone")
    user = signed_in(app, Role.ADMIN)

    assert register_phone(user, "shared-phone", TestPhone()).status_code == 404
    assert register_phone(user, "no-such-phone", TestPhone()).status_code == 404


def test_a_revoked_phone_is_refused_and_loses_its_endpoint(
    app: FastAPI, client: TestClient
) -> None:
    user = signed_in(app, Role.VIEWER)
    device_id = set_up_phone(user)
    register_phone(user, device_id, TestPhone())

    client.delete(f"/api/v1/devices/{device_id}", headers=admin())

    assert register_phone(user, device_id, TestPhone()).status_code == 404
    # Re-enabled with a new token, it isn't registered until it registers again.
    client.post(f"/api/v1/devices/{device_id}/rotate", headers=admin())
    assert _test(user, device_id).status_code == 409


def test_an_unlinked_phone_loses_its_endpoint(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    made = user.post("/api/v1/devices/mine", json={"name": "Pixel"}, headers=CSRF).json()
    register_phone(user, made["id"], TestPhone())

    client.post("/api/v1/devices/unlink", headers=bearer(made["token"]))
    client.post(f"/api/v1/devices/{made['id']}/rotate", headers=admin())

    assert _test(user, made["id"]).status_code == 409


def test_a_device_token_alone_or_no_sign_in_is_refused(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    made = user.post("/api/v1/devices/mine", json={"name": "Pixel"}, headers=CSRF).json()
    path = endpoint_path(made["id"])
    body = TestPhone().subscription()

    assert client.put(path, json=body, headers=bearer(made["token"])).status_code == 403
    assert client.delete(path, headers=bearer(made["token"])).status_code == 403
    assert client.post(f"{path}/test", headers=bearer(made["token"])).status_code == 403
    assert browser(app).put(path, json=body, headers=CSRF).status_code == 401
    # The signed-in session still needs the app's header.
    assert user.put(path, json=body).status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"endpoint": "http://push.example.com/up/abc"},
        {"endpoint": "https://"},
        {"endpoint": "https://push.example.com/" + "a" * 2048},
        {"p256dh": "not base64!"},
        {"p256dh": "AAAA"},
        {"auth": "AAAA"},
        {"route": "carrier_pigeon"},
        {"extra": "field"},
    ],
)
def test_a_bad_registration_is_refused(
    app: FastAPI, client: TestClient, change: dict[str, str]
) -> None:
    user = signed_in(app, Role.VIEWER)
    device_id = set_up_phone(user)

    body = {**TestPhone().subscription(), **change}
    response = user.put(endpoint_path(device_id), json=body, headers=CSRF)

    assert response.status_code == 422


def test_account_says_whether_the_user_has_a_registered_phone(
    app: FastAPI, client: TestClient
) -> None:
    user = signed_in(app, Role.VIEWER)
    assert user.get(ACCOUNT).json()["phone_registered"] is False
    device_id = set_up_phone(user)
    assert user.get(ACCOUNT).json()["phone_registered"] is False

    register_phone(user, device_id, TestPhone())
    assert user.get(ACCOUNT).json()["phone_registered"] is True

    user.delete(endpoint_path(device_id), headers=CSRF)
    assert user.get(ACCOUNT).json()["phone_registered"] is False
