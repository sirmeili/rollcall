"""Suggestion emails: each Editor and Admin with an address who chose Suggestion by email (off
by default) is emailed when someone suggests a product or catalog color for the shopping
list, except the one who suggested it. Adding or dismissing a suggestion sends nothing."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_shopping_list import JADE, LIST, _jade_white_in_the_catalog
from test_shopping_list_by_hand import _black

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

# The request email tests' helpers: email set up, choosing a kind, and what was sent.
sys.path.insert(0, str(Path(__file__).parent / "requests"))

from email_helpers import PUBLIC_URL, email_on, notify, sent  # noqa: E402

SUGGESTIONS = f"{LIST}/suggestions"
ACCOUNT = "/api/v1/auth/me"
FOOTER = "You can change these on your Account page."


@pytest.fixture
def outbox() -> FakeOutbox:
    """Where the server's emails go instead of a mail server."""
    return FakeOutbox()


@pytest.fixture
def app(db_url: str, outbox: FakeOutbox) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    return create_app(settings, mail_transport=outbox)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        yield client


def _person(app: FastAPI, username: str, role: Role, *, suggestion: bool = True) -> TestClient:
    """A signed-in user with an address, who chose Suggestion emails (if their role may)."""
    user = signed_in(app, role, username=username)
    user.patch(ACCOUNT, json={"email": f"{username}@example.com"}, headers=CSRF)
    if suggestion:
        notify(user, "suggestion", True)
    return user


def _suggest(user: TestClient, **body: object) -> dict:
    response = user.post(SUGGESTIONS, json=body, headers=CSRF)
    assert response.status_code == 200, response.text
    return response.json()


def test_an_editor_who_chose_suggestions_is_emailed_about_a_suggested_product(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "eddie", Role.EDITOR)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    black = _black(db)

    _suggest(vic, product_id=black.id, spools=2)

    [message] = sent(app, outbox)
    assert message["To"] == "eddie@example.com"
    assert message["Subject"] == "New suggestion from vic: Black"
    link = f"{PUBLIC_URL}/shopping-list"
    assert text_of(message) == (
        "vic suggested 2 spools of Black for the shopping list.\n"
        "\n"
        f"Open the shopping list: {link}\n"
        "\n"
        f"{FOOTER}\n"
    )
    html = html_of(message)
    assert f'<a href="{link}">Open the shopping list</a>' in html
    assert f"<p>{FOOTER}</p>" in html


def test_a_suggested_catalog_color_is_named_with_its_line(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "boss", Role.ADMIN)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    _jade_white_in_the_catalog(db)

    _suggest(vic, catalog_color=JADE, spools=1)

    [message] = sent(app, outbox)
    assert message["Subject"] == "New suggestion from vic: Jade White PLA Basic"
    assert text_of(message).startswith(
        "vic suggested 1 spool of Jade White PLA Basic for the shopping list.\n"
    )


def test_a_suggestion_from_a_token_names_nobody(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "boss", Role.ADMIN)
    black = _black(db)

    response = client.post(SUGGESTIONS, json={"product_id": black.id, "spools": 1}, headers=admin())

    assert response.status_code == 200
    [message] = sent(app, outbox)
    assert message["Subject"] == "New suggestion: Black"
    assert text_of(message).startswith(
        "Someone suggested 1 spool of Black for the shopping list.\n"
    )


def test_only_editors_and_admins_who_chose_it_are_emailed_never_the_suggester(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "boss", Role.ADMIN)
    _person(app, "eddie", Role.EDITOR)
    _person(app, "untouched_admin", Role.ADMIN, suggestion=False)
    _person(app, "untouched_editor", Role.EDITOR, suggestion=False)
    switched_off = _person(app, "switched_off", Role.EDITOR)
    notify(switched_off, "suggestion", False)
    no_address = signed_in(app, Role.ADMIN, username="no_address")
    notify(no_address, "suggestion", True)
    disabled = _person(app, "disabled", Role.ADMIN)
    disabled_id = disabled.get(ACCOUNT).json()["id"]
    client.patch(f"/api/v1/users/{disabled_id}", json={"disabled": True}, headers=admin())
    _person(app, "vic", Role.VIEWER, suggestion=False)
    frank = _person(app, "frank", Role.EDITOR)
    black = _black(db)

    _suggest(frank, product_id=black.id, spools=1)

    assert sorted(m["To"] for m in sent(app, outbox)) == ["boss@example.com", "eddie@example.com"]


def test_a_viewer_cant_choose_suggestion_emails(app: FastAPI, client: TestClient) -> None:
    vic = signed_in(app, Role.VIEWER, username="vic")

    response = vic.patch(
        ACCOUNT,
        json={"notifications": [{"kind": "suggestion", "channel": "email", "on": True}]},
        headers=CSRF,
    )

    assert response.status_code == 403


def test_adding_or_dismissing_a_suggestion_sends_nothing(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "boss", Role.ADMIN)
    eddie = _person(app, "eddie", Role.EDITOR)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    black = _black(db)
    first = _suggest(vic, product_id=black.id, spools=1)["suggestions"][0]["id"]
    second = _suggest(vic, product_id=black.id, spools=2)["suggestions"][1]["id"]
    sent(app, outbox)

    assert eddie.post(f"{SUGGESTIONS}/{first}/add", headers=CSRF).status_code == 200
    assert eddie.post(f"{SUGGESTIONS}/{second}/dismiss", headers=CSRF).status_code == 200

    assert sent(app, outbox) == []


def test_without_a_public_url_the_email_has_no_link(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client, public_url="")
    _person(app, "boss", Role.ADMIN)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    black = _black(db)

    _suggest(vic, product_id=black.id, spools=1)

    [message] = sent(app, outbox)
    assert text_of(message) == (
        f"vic suggested 1 spool of Black for the shopping list.\n\n{FOOTER}\n"
    )
    assert "http" not in html_of(message)


def test_links_ignore_the_requests_host_header(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "boss", Role.ADMIN)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    black = _black(db)

    response = vic.post(
        SUGGESTIONS,
        json={"product_id": black.id, "spools": 1},
        headers={**CSRF, "Host": "evil.example.net"},
    )

    assert response.status_code == 200
    [message] = sent(app, outbox)
    assert "evil.example.net" not in text_of(message)
    assert f"{PUBLIC_URL}/shopping-list" in text_of(message)


def test_with_email_off_nothing_is_sent_and_suggesting_still_works(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    _person(app, "boss", Role.ADMIN)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    black = _black(db)

    body = _suggest(vic, product_id=black.id, spools=1)

    assert len(body["suggestions"]) == 1
    assert outbox.sent == []


def test_a_failing_transport_never_fails_a_suggestion(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db: Session
) -> None:
    email_on(client)
    _person(app, "boss", Role.ADMIN)
    vic = _person(app, "vic", Role.VIEWER, suggestion=False)
    black = _black(db)
    outbox.fail()

    body = _suggest(vic, product_id=black.id, spools=1)

    assert len(body["suggestions"]) == 1
