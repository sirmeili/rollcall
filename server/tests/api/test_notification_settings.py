"""Notification settings on the account: the kinds the user's role can see, each with an Email
switch that is on or off by default until the user chooses."""

from dataclasses import replace

import pytest
from api_helpers import CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import NotificationKind, Role
from filament_tracker.notifications.kinds import KINDS

ACCOUNT = "/api/v1/auth/me"


def _setting(kind: str, on: bool, *, default: bool = True) -> dict[str, object]:
    return {"kind": kind, "channel": "email", "on": on, "default": default}


def test_a_viewer_who_isnt_a_requester_has_only_low_stock(app: FastAPI, client: TestClient) -> None:
    me = signed_in(app, Role.VIEWER).get(ACCOUNT).json()

    assert me["notifications"] == [_setting("low_stock", False)]


def test_a_requester_hears_about_their_requests_by_default(
    app: FastAPI, client: TestClient
) -> None:
    me = signed_in(app, Role.VIEWER, requester=True).get(ACCOUNT).json()

    assert me["notifications"] == [
        _setting("request_update", True),
        _setting("new_photo", True),
        _setting("low_stock", False),
    ]


def test_new_requests_are_on_for_admins_and_off_for_editors(
    app: FastAPI, client: TestClient
) -> None:
    editor = signed_in(app, Role.EDITOR).get(ACCOUNT).json()
    boss = signed_in(app, Role.ADMIN, requester=True).get(ACCOUNT).json()

    assert editor["notifications"] == [
        _setting("new_request", False),
        _setting("low_stock", False),
        _setting("suggestion", False),
    ]
    assert boss["notifications"] == [
        _setting("new_request", True),
        _setting("request_update", True),
        _setting("new_photo", True),
        _setting("low_stock", False),
        _setting("suggestion", False),
        _setting("backup_failed", False),
    ]


def test_suggestions_are_for_editors_and_admins_and_off_by_default(
    app: FastAPI, client: TestClient
) -> None:
    viewer = signed_in(app, Role.VIEWER, requester=True).get(ACCOUNT).json()
    editor = signed_in(app, Role.EDITOR).get(ACCOUNT).json()
    boss = signed_in(app, Role.ADMIN).get(ACCOUNT).json()

    assert _setting("suggestion", False) not in viewer["notifications"]
    assert _setting("suggestion", False) in editor["notifications"]
    assert _setting("suggestion", False) in boss["notifications"]


def test_backup_failed_is_for_admins_only_and_off_by_default(
    app: FastAPI, client: TestClient
) -> None:
    editor = signed_in(app, Role.EDITOR).get(ACCOUNT).json()
    boss = signed_in(app, Role.ADMIN).get(ACCOUNT).json()

    assert "backup_failed" not in [s["kind"] for s in editor["notifications"]]
    assert _setting("backup_failed", False) in boss["notifications"]


def test_the_old_switches_are_gone(app: FastAPI, client: TestClient) -> None:
    me = signed_in(app, Role.ADMIN).get(ACCOUNT).json()

    assert "email_on_request_change" not in me
    assert "email_on_new_request" not in me


def test_account_says_whether_email_is_set_up(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER)
    assert user.get(ACCOUNT).json()["email_set_up"] is False

    values = {"smtp_host": "smtp.example.com"}
    client.put("/api/v1/settings/email", json={"values": values}, headers=admin())

    assert user.get(ACCOUNT).json()["email_set_up"] is True


def test_a_user_turns_a_notification_off_and_on(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.ADMIN, requester=True)

    off = user.patch(
        ACCOUNT,
        json={
            "notifications": [
                {"kind": "new_request", "channel": "email", "on": False},
                {"kind": "new_photo", "channel": "email", "on": False},
            ]
        },
        headers=CSRF,
    )

    assert off.status_code == 200
    assert off.json()["notifications"] == [
        _setting("new_request", False, default=False),
        _setting("request_update", True),
        _setting("new_photo", False, default=False),
        _setting("low_stock", False),
        _setting("suggestion", False),
        _setting("backup_failed", False),
    ]
    back = user.patch(
        ACCOUNT,
        json={"notifications": [{"kind": "new_request", "channel": "email", "on": True}]},
        headers=CSRF,
    ).json()
    assert back["notifications"][0] == _setting("new_request", True, default=False)
    assert user.get(ACCOUNT).json()["notifications"] == back["notifications"]


def test_an_editor_can_choose_new_request_emails(app: FastAPI, client: TestClient) -> None:
    editor = signed_in(app, Role.EDITOR)

    me = editor.patch(
        ACCOUNT,
        json={"notifications": [{"kind": "new_request", "channel": "email", "on": True}]},
        headers=CSRF,
    ).json()

    assert me["notifications"] == [
        _setting("new_request", True, default=False),
        _setting("low_stock", False),
        _setting("suggestion", False),
    ]


def test_a_kind_outside_the_role_is_refused_and_nothing_changes(
    app: FastAPI, client: TestClient
) -> None:
    viewer = signed_in(app, Role.VIEWER, requester=True)

    response = viewer.patch(
        ACCOUNT,
        json={
            "notifications": [
                {"kind": "new_photo", "channel": "email", "on": False},
                {"kind": "new_request", "channel": "email", "on": True},
            ]
        },
        headers=CSRF,
    )

    assert response.status_code == 403
    assert viewer.get(ACCOUNT).json()["notifications"] == [
        _setting("request_update", True),
        _setting("new_photo", True),
        _setting("low_stock", False),
    ]


def test_a_kind_nothing_sends_yet_is_refused(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsent = replace(KINDS[NotificationKind.BACKUP_FAILED], sent=False)
    monkeypatch.setitem(KINDS, NotificationKind.BACKUP_FAILED, unsent)
    boss = signed_in(app, Role.ADMIN)

    response = boss.patch(
        ACCOUNT,
        json={"notifications": [{"kind": "backup_failed", "channel": "email", "on": True}]},
        headers=CSRF,
    )

    assert response.status_code == 403


def test_an_unknown_kind_or_channel_is_refused(app: FastAPI, client: TestClient) -> None:
    boss = signed_in(app, Role.ADMIN)

    for choice in (
        {"kind": "everything", "channel": "email", "on": True},
        {"kind": "new_request", "channel": "pigeon", "on": True},
    ):
        response = boss.patch(ACCOUNT, json={"notifications": [choice]}, headers=CSRF)
        assert response.status_code == 422


def test_choices_kept_when_the_role_changes_apply_again(app: FastAPI, client: TestClient) -> None:
    editor = signed_in(app, Role.EDITOR)
    editor_id = editor.get(ACCOUNT).json()["id"]
    editor.patch(
        ACCOUNT,
        json={"notifications": [{"kind": "new_request", "channel": "email", "on": True}]},
        headers=CSRF,
    )

    client.patch(f"/api/v1/users/{editor_id}", json={"role": "viewer"}, headers=admin())
    assert editor.get(ACCOUNT).json()["notifications"] == [_setting("low_stock", False)]
    client.patch(f"/api/v1/users/{editor_id}", json={"role": "editor"}, headers=admin())

    assert editor.get(ACCOUNT).json()["notifications"] == [
        _setting("new_request", True, default=False),
        _setting("low_stock", False),
        _setting("suggestion", False),
    ]


def test_changing_a_notification_keeps_the_address(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.VIEWER, requester=True)
    user.patch(ACCOUNT, json={"email": "sam@example.com"}, headers=CSRF)

    me = user.patch(
        ACCOUNT,
        json={"notifications": [{"kind": "new_photo", "channel": "email", "on": False}]},
        headers=CSRF,
    ).json()

    assert me["email"] == "sam@example.com"
