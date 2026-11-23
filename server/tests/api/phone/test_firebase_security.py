"""Security suite: the Firebase service-account key is never returned or logged, and can't be
read without the settings key; its OAuth access tokens and a phone's FCM token are never
logged; only an Admin reads or changes the Firebase settings (from the LAN or not)."""

import logging

import pytest
from api_helpers import CSRF, INTERNET_CLIENT, admin, bearer, signed_in
from fake_push_outbox import FIREBASE, FakePushOutbox, FcmPhone, service_account
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import CONFIG, endpoint_path, pushed, set_up_phone
from request_helpers import person, submitted

from filament_tracker.app_settings.crypto import SecretBox, Unreadable, new_key_text, parse_key
from filament_tracker.db.models import Setting
from filament_tracker.domain.enums import Role

URL = "/api/v1/settings/phone-notifications"
KEY = "firebase_service_account"


def _set_up(client: TestClient) -> str:
    key = service_account().json
    response = client.put(URL, json={"values": {**FIREBASE, KEY: key}}, headers=admin())
    assert response.status_code == 200
    return key


def _pem_body(key: str) -> str:
    """A line from the middle of the key's PEM: what would show if any of it leaked."""
    return key.split("\\n")[5]


def test_the_key_is_never_returned_or_logged(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    key = _set_up(client)
    frank = person(app, "frank", Role.ADMIN, requester=False)
    phone = FcmPhone()
    phone.device_id = set_up_phone(frank)
    frank.put(endpoint_path(phone.device_id), json=phone.subscription(), headers=CSRF)

    submitted(person(app, "sam"), title="Lamp")
    pushed(app, pushes)
    responses = [
        client.get(URL, headers=admin()),
        frank.get(URL),
        frank.get(CONFIG),
        frank.post(f"{endpoint_path(phone.device_id)}/test", headers=CSRF),
        client.get("/openapi.json"),
    ]

    secret = _pem_body(key)
    assert len(secret) > 40
    for response in responses:
        assert secret not in response.text
        assert "PRIVATE KEY" not in response.text
    for text in (secret, "PRIVATE KEY", "fake-access-token", phone.token):
        assert text not in caplog.text


def test_the_key_is_stored_sealed_and_unreadable_without_the_settings_key(
    app: FastAPI, client: TestClient
) -> None:
    key = _set_up(client)
    with app.state.session_factory() as session:
        stored = session.get(Setting, KEY)

    assert stored is not None and stored.secret
    assert _pem_body(key) not in stored.value
    with pytest.raises(Unreadable):
        SecretBox(parse_key(new_key_text())).open(KEY, stored.value)


def test_a_bad_key_is_refused_without_repeating_any_of_it(client: TestClient) -> None:
    key = service_account().json.replace("service_account", "authorized_user")

    response = client.put(URL, json={"values": {KEY: key}}, headers=admin())

    assert response.status_code == 422
    assert _pem_body(key) not in response.text


def test_only_an_admin_reads_or_changes_firebase(app: FastAPI, client: TestClient) -> None:
    viewer = signed_in(app, Role.VIEWER, username="vic")
    editor = signed_in(app, Role.EDITOR, username="eddie")
    away = signed_in(app, Role.ADMIN, INTERNET_CLIENT, username="away")

    for user in (viewer, editor):
        assert user.get(URL).status_code == 403
        assert user.put(URL, json={"values": FIREBASE}, headers=CSRF).status_code == 403
        assert user.delete(f"{URL}/{KEY}", headers=CSRF).status_code == 403
    # An Admin's session works from anywhere, as for every settings group; a bearer token
    # from outside the LAN doesn't.
    assert away.get(URL).status_code == 200
    assert away.get(URL, headers=bearer("not-a-token")).status_code == 403
