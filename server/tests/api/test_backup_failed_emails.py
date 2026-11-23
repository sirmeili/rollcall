"""Backup failed emails: when a nightly backup fails, each Admin with an address who chose
Backup failed by email (off by default) is emailed the reason, with a link to Settings. The
backup job is run with a failing destination, as the backup tests do."""

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from api_helpers import ADMIN_TOKEN, CSRF, admin, signed_in
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

# The request email tests' helpers: email set up, and the emails the server sent.
sys.path.insert(0, str(Path(__file__).parent / "requests"))

from email_helpers import email_on, notify, sent  # noqa: E402

ACCOUNT = "/api/v1/auth/me"
FOOTER = "You can change these on your Account page."
SETTINGS_LINK = "https://rollcall.example.com/settings"
LAST_NIGHT = datetime(2026, 11, 10, 3, 0, tzinfo=UTC)


@pytest.fixture
def outbox() -> FakeOutbox:
    return FakeOutbox()


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    """A file where the backup folder should be, so every backup fails."""
    folder = tmp_path / "backups"
    folder.write_text("a file where the folder should be")
    return folder


@pytest.fixture
def app(db_url: str, outbox: FakeOutbox, backup_dir: Path) -> FastAPI:
    settings = Settings(
        database_url=db_url, admin_token=ADMIN_TOKEN, backup_dir=backup_dir, _env_file=None
    )
    return create_app(settings, mail_transport=outbox)


def _person(app: FastAPI, username: str, role: Role, *, chose_it: bool = True) -> TestClient:
    user = signed_in(app, role, username=username)
    user.patch(ACCOUNT, json={"email": f"{username}@example.com"}, headers=CSRF)
    if chose_it:
        notify(user, "backup_failed", True)
    return user


def _back_up(app: FastAPI) -> Path | None:
    """Run last night's backup now."""
    return app.state.backups.run_once(LAST_NIGHT)


def test_each_admin_who_chose_it_is_emailed_the_reason(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    _person(app, "mia", Role.ADMIN)

    assert _back_up(app) is None

    emails = sent(app, outbox)
    assert sorted(m["To"] for m in emails) == ["frank@example.com", "mia@example.com"]
    message = emails[0]
    assert message["Subject"] == "Backup failed"
    sentence, link, footer = text_of(message).split("\n\n")
    # The reason is the error's one line: the backup folder is a file.
    assert re.fullmatch(r"Last night's backup failed: [^\n]*exists[^\n]*backups'?\.", sentence)
    assert link == f"Open Settings: {SETTINGS_LINK}"
    assert footer == f"{FOOTER}\n"
    assert f'<a href="{SETTINGS_LINK}">Open Settings</a>' in html_of(message)


def test_only_admins_who_chose_it_and_can_be_emailed_are(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    _person(app, "untouched", Role.ADMIN, chose_it=False)
    switched_off = _person(app, "switched_off", Role.ADMIN)
    notify(switched_off, "backup_failed", False)
    no_address = signed_in(app, Role.ADMIN, username="no_address")
    notify(no_address, "backup_failed", True)
    disabled = _person(app, "disabled", Role.ADMIN)
    disabled_id = disabled.get(ACCOUNT).json()["id"]
    client.patch(f"/api/v1/users/{disabled_id}", json={"disabled": True}, headers=admin())
    _person(app, "eddie", Role.EDITOR, chose_it=False)
    _person(app, "vic", Role.VIEWER, chose_it=False)

    _back_up(app)

    assert [m["To"] for m in sent(app, outbox)] == ["frank@example.com"]


def test_no_link_without_a_public_url(app: FastAPI, client: TestClient, outbox: FakeOutbox) -> None:
    email_on(client, public_url="")
    _person(app, "frank", Role.ADMIN)

    _back_up(app)

    [message] = sent(app, outbox)
    assert text_of(message).endswith(f".\n\n{FOOTER}\n")
    assert "http" not in html_of(message)


def test_a_successful_backup_sends_nothing(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, backup_dir: Path
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    backup_dir.unlink()

    assert _back_up(app) is not None

    assert sent(app, outbox) == []


def test_no_email_while_email_is_off(app: FastAPI, client: TestClient, outbox: FakeOutbox) -> None:
    _person(app, "frank", Role.ADMIN)
    email_on(client, smtp_host="")

    _back_up(app)

    email_on(client)  # So the check below can see what was sent.
    assert sent(app, outbox) == []


def test_a_failing_transport_never_affects_the_backups(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, backup_dir: Path
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    outbox.fail()

    assert _back_up(app) is None
    backup_dir.unlink()

    assert _back_up(app) is not None
