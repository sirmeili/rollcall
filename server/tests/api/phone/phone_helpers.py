"""Helpers for the phone notification tests: a user's phone set up and registered for phone
notifications, and the Web Pushes the server sent."""

import time
from typing import Any

from api_helpers import CSRF
from fake_push_outbox import FakePushOutbox, TestPhone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.push.webpush import PushMessage

CONFIG = "/api/v1/push/config"


def endpoint_path(device_id: str) -> str:
    return f"/api/v1/push/devices/{device_id}"


def set_up_phone(user: TestClient, name: str = "Pixel 9") -> str:
    """The signed-in user sets up their phone at home; its device ID."""
    response = user.post("/api/v1/devices/mine", json={"name": name}, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def register_phone(user: TestClient, device_id: str, phone: TestPhone) -> Any:
    return user.put(endpoint_path(device_id), json=phone.subscription(), headers=CSRF)


def users_phone(user: TestClient, endpoint: str = "https://push.example.com/up/abc") -> TestPhone:
    """Set up the signed-in user's phone and register it for phone notifications."""
    phone = TestPhone(endpoint)
    phone.device_id = set_up_phone(user)
    response = register_phone(user, phone.device_id, phone)
    assert response.status_code == 200, response.text
    return phone


def pushed(app: FastAPI, pushes: FakePushOutbox, timeout: float = 5.0) -> list[PushMessage]:
    """The Web Pushes the server sent since the last call, once it has tried everything
    queued."""
    sender = app.state.push
    deadline = time.monotonic() + timeout
    while not sender.idle():
        assert time.monotonic() < deadline, "timed out waiting for the pushes"
        time.sleep(0.005)
    found = list(pushes.sent)
    pushes.sent.clear()
    return found


def to(phone: TestPhone, messages: list[PushMessage]) -> list[dict[str, Any]]:
    """The payloads sent to `phone`, decrypted with its keys."""
    return [phone.decrypt(m) for m in messages if m.endpoint == phone.endpoint]
