"""The Email settings group, Send test email and the sender's last success and failure."""

import logging
from typing import Any

import pytest
from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app
from filament_tracker.services.cooldown import TEST_EMAIL_GAP, Cooldown

URL = "/api/v1/settings/email"
TEST_URL = f"{URL}/test"
STATUS_URL = f"{URL}/status"
PASSWORD = "smtp-password-value-1234"  # noqa: S105 - test value
SETUP = {
    "smtp_host": "smtp.example.com",
    "smtp_port": "465",
    "smtp_security": "tls",
    "smtp_user": "rollcall@example.com",
    "smtp_password": PASSWORD,
    "smtp_from": "RollCall <rollcall@example.com>",
    "public_url": "https://rollcall.example.com/",
}


def by_key(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in body["settings"]}


@pytest.fixture
def outbox() -> FakeOutbox:
    return FakeOutbox()


class FakeClock:
    """The test email cooldown's clock, moved by hand so no test sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(db_url: str, outbox: FakeOutbox, clock: FakeClock) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    app = create_app(settings, mail_transport=outbox)
    app.state.test_email_cooldown = Cooldown(TEST_EMAIL_GAP, clock=clock)
    return app


@pytest.fixture
def boss(app: FastAPI, client: TestClient) -> TestClient:
    """A signed-in Admin with an email address."""
    user = signed_in(app, Role.ADMIN, username="boss")
    user.patch("/api/v1/auth/me", json={"email": "boss@example.com"}, headers=CSRF)
    return user


def save(client: TestClient, values: dict[str, str]) -> Any:
    return client.put(URL, json={"values": values}, headers=admin())


def test_the_email_group_and_its_defaults(client: TestClient) -> None:
    response = client.get(URL, headers=admin())

    assert response.status_code == 200
    settings = by_key(response.json())
    assert list(settings) == [
        "smtp_host",
        "smtp_port",
        "smtp_security",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        "public_url",
    ]
    assert settings["smtp_port"]["value"] == "587"
    assert settings["smtp_security"]["value"] == "starttls"
    assert settings["smtp_host"]["set"] is False
    assert settings["smtp_password"]["secret"] is True


def test_saving_the_group_never_returns_or_logs_the_password(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    response = save(client, SETUP)

    assert response.status_code == 200
    assert PASSWORD not in response.text
    settings = by_key(response.json())
    password = settings["smtp_password"]
    assert (password["secret"], password["set"], password["value"]) == (True, True, None)
    assert settings["smtp_host"]["value"] == "smtp.example.com"
    assert settings["smtp_port"]["value"] == "465"
    assert settings["public_url"]["value"] == "https://rollcall.example.com"
    assert PASSWORD not in client.get(URL, headers=admin()).text
    assert PASSWORD not in caplog.text


def test_each_setting_can_come_from_the_environment(db_url: str) -> None:
    settings = Settings(
        database_url=db_url,
        admin_token=ADMIN_TOKEN,
        smtp_host="mail.example.com",
        smtp_port=2525,
        smtp_security="none",
        smtp_user="me",
        smtp_password=SecretStr(PASSWORD),
        smtp_from="me@example.com",
        public_url="https://rollcall.example.com",
        _env_file=None,
    )
    with TestClient(create_app(settings), base_url=BASE_URL, client=LAN_CLIENT) as client:
        response = client.get(URL, headers=admin())

    settings_out = by_key(response.json())
    assert {k: s["source"] for k, s in settings_out.items()} == dict.fromkeys(settings_out, "env")
    assert settings_out["smtp_port"]["value"] == "2525"
    assert settings_out["smtp_security"]["value"] == "none"
    assert PASSWORD not in response.text


@pytest.mark.parametrize(
    "values",
    [
        {"smtp_port": "0"},
        {"smtp_port": "65536"},
        {"smtp_port": "smtp"},
        {"smtp_security": "ssl"},
        {"smtp_security": ""},
        {"smtp_from": "not an address"},
        {"smtp_host": "smtp example com"},
        {"public_url": "http://rollcall.example.com"},
        {"public_url": "https://rollcall.example.com/requests"},
        {"public_url": "https://rollcall.example.com?x=1"},
        {"public_url": "https://user@rollcall.example.com"},
    ],
)
def test_bad_email_values_are_refused(client: TestClient, values: dict[str, str]) -> None:
    response = save(client, values)

    assert response.status_code == 422
    assert set(response.json()["detail"]["problems"]) == set(values)


def test_a_bad_from_address_is_refused_without_repeating_it(client: TestClient) -> None:
    response = save(client, {"smtp_from": "secret-looking-value"})

    assert response.status_code == 422
    assert "secret-looking-value" not in response.text


def test_send_test_email_sends_to_the_signed_in_admin(
    boss: TestClient, outbox: FakeOutbox, client: TestClient
) -> None:
    save(client, SETUP)

    response = boss.post(TEST_URL, headers=CSRF)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Sent a test email to boss@example.com."}
    [message] = outbox.sent
    assert message["To"] == "boss@example.com"
    assert message["From"] == "RollCall <rollcall@example.com>"
    assert "RollCall" in message["Subject"]
    assert "test email from RollCall" in text_of(message)
    assert "test email from RollCall" in html_of(message)
    [server] = outbox.servers
    assert (server.host, server.port, server.security) == ("smtp.example.com", 465, "tls")
    assert server.password is not None and server.password.get_secret_value() == PASSWORD


def test_send_test_email_reports_a_failure(
    boss: TestClient, outbox: FakeOutbox, client: TestClient
) -> None:
    save(client, SETUP)
    outbox.fail(message="The mail server refused the user name or password.")

    response = boss.post(TEST_URL, headers=CSRF)

    assert response.json() == {
        "ok": False,
        "message": "The mail server refused the user name or password.",
    }
    # It waits for the one result: no retries.
    assert outbox.attempts == 1


def test_send_test_email_with_no_host_sends_nothing(boss: TestClient, outbox: FakeOutbox) -> None:
    response = boss.post(TEST_URL, headers=CSRF)

    assert response.json() == {"ok": False, "message": "Email is off: no SMTP host is set."}
    assert outbox.attempts == 0


def test_send_test_email_needs_the_admins_address(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    save(client, SETUP)
    nobody = signed_in(app, Role.ADMIN, username="nobody")

    response = nobody.post(TEST_URL, headers=CSRF)

    assert response.json() == {
        "ok": False,
        "message": "Add your email address on Account first.",
    }
    assert outbox.attempts == 0


def test_send_test_email_needs_a_signed_in_admin(client: TestClient, outbox: FakeOutbox) -> None:
    save(client, SETUP)

    assert client.post(TEST_URL, headers=admin()).status_code == 403
    assert outbox.attempts == 0


def test_a_second_test_email_within_30_seconds_is_refused(
    boss: TestClient, outbox: FakeOutbox, client: TestClient, clock: FakeClock
) -> None:
    save(client, SETUP)
    outbox.fail(message="Can't reach the mail server. Check the host and port.")
    boss.post(TEST_URL, headers=CSRF)
    clock.now += 29

    response = boss.post(TEST_URL, headers=CSRF)

    # A failed test counts too: the second one is refused without trying the server.
    assert response.status_code == 429
    assert response.json()["detail"] == "Wait a few seconds before sending another test email."
    assert outbox.attempts == 1


def test_a_test_email_after_30_seconds_is_sent(
    boss: TestClient, outbox: FakeOutbox, client: TestClient, clock: FakeClock
) -> None:
    save(client, SETUP)
    boss.post(TEST_URL, headers=CSRF)
    clock.now += 30

    response = boss.post(TEST_URL, headers=CSRF)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(outbox.sent) == 2


def test_the_last_success_and_failure_are_shown(
    boss: TestClient, outbox: FakeOutbox, client: TestClient, clock: FakeClock
) -> None:
    assert boss.get(STATUS_URL).json() == {
        "on": False,
        "last_success": None,
        "last_failure": None,
    }
    save(client, SETUP)
    boss.post(TEST_URL, headers=CSRF)
    outbox.fail(message="Can't reach the mail server. Check the host and port.")
    clock.now += TEST_EMAIL_GAP
    boss.post(TEST_URL, headers=CSRF)

    status = boss.get(STATUS_URL).json()

    assert status["on"] is True
    assert status["last_success"] is not None
    assert status["last_failure"]["message"] == (
        "Can't reach the mail server. Check the host and port."
    )
    assert status["last_failure"]["at"] >= status["last_success"]
    assert PASSWORD not in boss.get(STATUS_URL).text
