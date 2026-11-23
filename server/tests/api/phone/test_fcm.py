"""Phone notifications through Google's push service (FCM), for phones of the google flavor:
registered with the phone's FCM token, sent with the HTTP v1 API and an OAuth access token
from the service-account key, with the same payload and failure rules as Web Push."""

import json
import time

import pytest
from api_helpers import CSRF, admin, signed_in
from fake_push_outbox import (
    FCM,
    FIREBASE,
    FakePushOutbox,
    FcmPhone,
    ServiceAccount,
    assertion_claims,
    service_account,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import endpoint_path, pushed, set_up_phone
from request_helpers import person, submitted

from filament_tracker.domain.enums import Role

SETTINGS = "/api/v1/settings/phone-notifications"
TITLE = "Lithophane lamp shade"
SEND_URL = f"{FCM}rollcall-test/messages:send"


@pytest.fixture
def account(client: TestClient) -> ServiceAccount:
    """Firebase set up on the Settings page."""
    account = service_account()
    values = {**FIREBASE, "firebase_service_account": account.json}
    assert client.put(SETTINGS, json={"values": values}, headers=admin()).status_code == 200
    return account


def fcm_phone(user: TestClient, token: str = "fcm-token_abc:123-XYZ") -> FcmPhone:  # noqa: S107
    phone = FcmPhone(token)
    phone.device_id = set_up_phone(user)
    response = user.put(endpoint_path(phone.device_id), json=phone.subscription(), headers=CSRF)
    assert response.status_code == 200, response.text
    assert response.json()["route"] == "fcm"
    return phone


def _test(user: TestClient, device_id: str) -> dict[str, object]:
    return user.post(f"{endpoint_path(device_id)}/test", headers=CSRF).json()


def test_a_phone_registers_its_fcm_token_and_gets_a_test_notification(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, account: ServiceAccount
) -> None:
    user = signed_in(app, Role.VIEWER)
    phone = fcm_phone(user)

    assert _test(user, phone.device_id) == {
        "ok": True,
        "message": "Sent a test notification to this phone.",
    }

    [message] = pushes.sent
    assert message.endpoint == SEND_URL
    assert message.headers["Authorization"] == "Bearer fake-access-token-1"
    assert message.headers["Content-Type"] == "application/json"
    assert json.loads(message.body) == {
        "message": {
            "token": phone.token,
            "data": {
                "kind": "test",
                "title": "Test notification",
                "text": "Phone notifications work on this phone.",
                "path": "/",
            },
            "android": {"priority": "high", "ttl": f"{7 * 24 * 3600}s"},
        }
    }


def test_the_access_token_is_asked_for_with_the_service_account_key(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, account: ServiceAccount
) -> None:
    user = signed_in(app, Role.VIEWER)
    phone = fcm_phone(user)

    _test(user, phone.device_id)

    [assertion] = pushes.assertions
    claims = assertion_claims(assertion, account)
    assert claims["iss"] == account.email
    assert claims["scope"] == "https://www.googleapis.com/auth/firebase.messaging"
    assert claims["aud"] == "https://oauth2.googleapis.com/token"
    assert claims["iat"] <= time.time() < claims["exp"] <= claims["iat"] + 3600


def test_the_access_token_is_kept_until_it_nearly_expires(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, account: ServiceAccount
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    fcm_phone(frank)
    sam = person(app, "sam")

    submitted(sam, title=TITLE)
    submitted(sam, title="Again")
    pushed(app, pushes)

    assert len(pushes.assertions) == 1


def test_a_notification_reaches_an_fcm_phone_with_the_web_push_payload(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, account: ServiceAccount
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    phone = fcm_phone(frank)

    request_id = submitted(person(app, "sam"), title=TITLE)["id"]

    assert phone.data(pushed(app, pushes)) == [
        {
            "kind": "new_request",
            "title": f"New print request from sam: {TITLE}",
            "text": f'sam submitted a new print request: "{TITLE}".',
            "path": f"/requests/{request_id}",
        }
    ]


def test_an_unregistered_token_is_dropped_at_once(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, account: ServiceAccount
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    fcm_phone(frank)
    sam = person(app, "sam")
    # FCM answers 404 (UNREGISTERED) for a token whose app was uninstalled.
    pushes.answer(404)
    submitted(sam, title=TITLE)
    assert pushed(app, pushes) == []
    attempts = pushes.attempts

    submitted(sam, title="Again")
    pushed(app, pushes)

    assert pushes.attempts == attempts


def test_without_firebase_an_fcm_phone_gets_nothing(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    user = signed_in(app, Role.VIEWER)
    phone = fcm_phone(user)

    result = _test(user, phone.device_id)

    assert result == {"ok": False, "message": "Firebase isn't set up on this server."}
    assert pushes.attempts == 0


def test_a_refused_key_is_a_failure_that_never_repeats_google(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox, account: ServiceAccount
) -> None:
    user = signed_in(app, Role.VIEWER)
    phone = fcm_phone(user)
    pushes.refuse_tokens()

    result = _test(user, phone.device_id)

    assert result == {"ok": False, "message": "Google refused the Firebase service-account key."}


@pytest.mark.parametrize(
    "body",
    [
        {"route": "fcm", "endpoint": "has spaces"},
        {"route": "fcm", "endpoint": ""},
        {"route": "fcm", "endpoint": "x" * 4097},
        {"route": "fcm", "endpoint": "token", "p256dh": "BAAA", "auth": "AAAA"},
        {"route": "web_push", "endpoint": "https://push.example.com/up/abc"},
    ],
)
def test_a_badly_formed_registration_is_refused(
    app: FastAPI, client: TestClient, body: dict[str, str]
) -> None:
    user = signed_in(app, Role.VIEWER)
    device_id = set_up_phone(user)

    assert user.put(endpoint_path(device_id), json=body, headers=CSRF).status_code == 422
