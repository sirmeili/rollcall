"""New-request emails: every Admin with an address and the switch on is emailed about each
new request, except the one who submitted it."""

from datetime import date, timedelta

from api_helpers import CSRF, admin
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import person, submitted

from filament_tracker.domain.enums import Role

TITLE = "Lithophane lamp shade"
ACCOUNT = "/api/v1/auth/me"


def _person(app: FastAPI, username: str, role: Role, *, requester: bool = False) -> TestClient:
    user = person(app, username, role, requester=requester)
    user.patch(ACCOUNT, json={"email": f"{username}@example.com"}, headers=CSRF)
    return user


def test_each_admin_is_emailed_about_a_new_request(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    _person(app, "mia", Role.ADMIN)
    sam = _person(app, "sam", Role.VIEWER, requester=True)
    needed_by = date.today() + timedelta(days=30)

    request = submitted(sam, title=TITLE, priority="urgent", needed_by=needed_by.isoformat())

    emails = sent(app, outbox)
    assert sorted(m["To"] for m in emails) == ["frank@example.com", "mia@example.com"]
    message = emails[0]
    assert message["Subject"] == f"New print request from sam: {TITLE}"
    link = f"https://rollcall.example.com/requests/{request['id']}"
    day = f"{needed_by.day} {needed_by:%b %Y}"
    assert text_of(message) == (
        f'sam submitted a new print request: "{TITLE}".\n'
        "\n"
        "Priority: Urgent\n"
        f"Needed by: {day}\n"
        "\n"
        f"Open the request: {link}\n"
    )
    html = html_of(message)
    assert "<strong>Priority:</strong> Urgent" in html
    assert f'<a href="{link}">Open the request</a>' in html
    assert "Account page" not in text_of(message)


def test_no_needed_by_line_without_a_date(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client, public_url="")
    _person(app, "frank", Role.ADMIN)
    sam = _person(app, "sam", Role.VIEWER, requester=True)

    submitted(sam, title=TITLE)

    [message] = sent(app, outbox)
    assert text_of(message) == (
        f'sam submitted a new print request: "{TITLE}".\n\nPriority: Normal\n'
    )
    assert "http" not in html_of(message)


def test_the_admin_who_submitted_it_isnt_emailed(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    boss = _person(app, "boss", Role.ADMIN, requester=True)

    submitted(boss)

    assert [m["To"] for m in sent(app, outbox)] == ["frank@example.com"]


def test_only_admins_who_can_and_want_to_be_emailed_are(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    person(app, "no_address", Role.ADMIN, requester=False)
    switched_off = _person(app, "switched_off", Role.ADMIN)
    switched_off.patch(ACCOUNT, json={"email_on_new_request": False}, headers=CSRF)
    disabled = _person(app, "disabled", Role.ADMIN)
    disabled_id = disabled.get(ACCOUNT).json()["id"]
    client.patch(f"/api/v1/users/{disabled_id}", json={"disabled": True}, headers=admin())
    _person(app, "eddie", Role.EDITOR)
    sam = _person(app, "sam", Role.VIEWER, requester=True)

    submitted(sam)

    assert [m["To"] for m in sent(app, outbox)] == ["frank@example.com"]


def test_a_failing_transport_never_fails_a_submit(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    _person(app, "frank", Role.ADMIN)
    sam = _person(app, "sam", Role.VIEWER, requester=True)
    outbox.fail()

    submitted(sam)
