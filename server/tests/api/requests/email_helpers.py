"""Helpers for the request email tests: email set up, and the emails the server sent."""

import time
from email.message import EmailMessage

from api_helpers import CSRF, admin
from fake_outbox import FakeOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.mail.message import Email

PUBLIC_URL = "https://rollcall.example.com"
SETUP = {
    "smtp_host": "smtp.example.com",
    "smtp_from": "RollCall <rollcall@example.com>",
    "public_url": PUBLIC_URL,
}
# Queued after everything else, so once it is sent, every email before it has been tried.
_MARKER = Email(to="marker@example.invalid", subject="marker", text="marker\n", html="marker")


def email_on(client: TestClient, **values: str) -> None:
    """Save the email settings: a host, a from address and the public URL, unless changed."""
    response = client.put(
        "/api/v1/settings/email", json={"values": {**SETUP, **values}}, headers=admin()
    )
    assert response.status_code == 200, response.text


def sent(app: FastAPI, outbox: FakeOutbox, timeout: float = 5.0) -> list[EmailMessage]:
    """The emails the server sent since the last call, once it has sent everything queued."""
    app.state.mail.send_later([_MARKER])
    deadline = time.monotonic() + timeout
    while not any(m["To"] == _MARKER.to for m in outbox.sent):
        assert time.monotonic() < deadline, "timed out waiting for the emails"
        time.sleep(0.005)
    found = [m for m in outbox.sent if m["To"] != _MARKER.to]
    outbox.sent.clear()
    return found


def notify(user: TestClient, kind: str, on: bool) -> None:
    """The signed-in user chooses whether to get `kind` by email."""
    response = user.patch(
        "/api/v1/auth/me",
        json={"notifications": [{"kind": kind, "channel": "email", "on": on}]},
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
