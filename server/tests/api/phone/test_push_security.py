"""Security suite: the VAPID private key is never returned or logged, and can't be read without
the settings key; a phone registers only as its own user's (the refusals are in
test_push_registration.py)."""

import logging

import pytest
from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, signed_in
from fake_push_outbox import FakePushOutbox, b64url
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import CONFIG, endpoint_path, pushed, users_phone
from pydantic import SecretStr
from request_helpers import person
from sqlalchemy import select

from filament_tracker.app_settings.crypto import SecretBox, Unreadable, new_key_text, parse_key
from filament_tracker.config import Settings
from filament_tracker.db.push_models import PushEndpoint, VapidKey
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app
from filament_tracker.push.keys import SEALED_AS

KEY = new_key_text()


def _private(app: FastAPI) -> str:
    """The private key as the server holds it, base64url."""
    private = app.state.vapid_keys.private
    return b64url(private.private_numbers().private_value.to_bytes(32, "big"))


def _app(db_url: str, pushes: FakePushOutbox, key: str = KEY) -> FastAPI:
    settings = Settings(
        database_url=db_url, admin_token=ADMIN_TOKEN, settings_key=SecretStr(key), _env_file=None
    )
    return create_app(settings, push_transport=pushes)


def test_the_private_key_is_never_returned_or_logged(
    db_url: str, pushes: FakePushOutbox, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    app = _app(db_url, pushes)
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        frank = person(app, "frank", Role.ADMIN, requester=False)
        phone = users_phone(frank)
        responses = [
            frank.get(CONFIG),
            frank.put(endpoint_path(phone.device_id), json=phone.subscription(), headers=CSRF),
            frank.post(f"{endpoint_path(phone.device_id)}/test", headers=CSRF),
            client.get("/openapi.json"),
        ]
        pushed(app, pushes)
        private = _private(app)

    for response in responses:
        assert private not in response.text
    assert private not in caplog.text
    assert repr(app.state.vapid_keys).count(private) == 0


def test_the_private_key_is_stored_sealed_and_unreadable_without_the_key(
    db_url: str, pushes: FakePushOutbox
) -> None:
    app = _app(db_url, pushes)
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT):
        private = _private(app)
        with app.state.session_factory() as session:
            stored = session.scalar(select(VapidKey))
    assert stored is not None
    assert private not in stored.private_key
    assert SecretBox(parse_key(KEY)).open(SEALED_AS, stored.private_key) == private
    with pytest.raises(Unreadable):
        SecretBox(parse_key(new_key_text())).open(SEALED_AS, stored.private_key)


def test_without_its_settings_key_a_new_pair_is_made_and_phones_register_again(
    db_url: str, pushes: FakePushOutbox
) -> None:
    app = _app(db_url, pushes)
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT):
        user = signed_in(app, Role.VIEWER, username="sam")
        phone = users_phone(user)
        before = user.get(CONFIG).json()["vapid_public_key"]

    app = _app(db_url, pushes, key=new_key_text())
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT):
        user = signed_in(app, Role.VIEWER, username="sam2")
        after = user.get(CONFIG).json()["vapid_public_key"]
        with app.state.session_factory() as session:
            assert session.get(PushEndpoint, phone.device_id) is None

    assert after != before
