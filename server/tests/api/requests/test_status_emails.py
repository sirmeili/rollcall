"""Status emails: the requester is emailed when an Admin moves their request on, as the
pipeline's "emails the requester" column says, read through the fake outbox."""

import time
from email.message import EmailMessage

import pytest
from api_helpers import CSRF, admin
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, edit, person, submitted
from sqlalchemy.orm import Session
from test_moves import move

from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import RequestStatus, Role

TITLE = "Lithophane lamp shade"
FOOTER = "You can turn these emails off on your Account page."


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    """A Requester with an email address."""
    user = person(app, "sam")
    user.patch("/api/v1/auth/me", json={"email": "sam@example.com"}, headers=CSRF)
    return user


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    """An Admin, not a Requester, with an email address."""
    user = person(app, "frank", Role.ADMIN, requester=False)
    user.patch("/api/v1/auth/me", json={"email": "frank@example.com"}, headers=CSRF)
    return user


@pytest.fixture
def request_id(
    app: FastAPI, client: TestClient, sam: TestClient, frank: TestClient, outbox: FakeOutbox
) -> int:
    """Sam's request, with email set up and the new-request email already sent."""
    email_on(client)
    request_id = submitted(sam, title=TITLE)["id"]
    sent(app, outbox)
    return request_id


def _in(db: Session, request_id: int, status: str) -> None:
    """Put the request in `status`, as the moves before it would have."""
    db.get(PrintRequest, request_id).status = RequestStatus(status)
    db.commit()


def _one(app: FastAPI, outbox: FakeOutbox) -> EmailMessage:
    [message] = sent(app, outbox)
    return message


def test_the_requester_is_emailed_when_their_request_is_approved(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    response = move(frank, request_id, "submitted", "approved", "  Next week.  ")

    assert response.status_code == 200, response.text
    message = _one(app, outbox)
    assert message["To"] == "sam@example.com"
    assert message["Subject"] == f"Your print request was approved: {TITLE}"
    link = f"https://rollcall.example.com/requests/{request_id}"
    assert text_of(message) == (
        f'Your print request "{TITLE}" was approved.\n'
        "\n"
        "Note: Next week.\n"
        "\n"
        f"Open the request: {link}\n"
        "\n"
        f"{FOOTER}\n"
    )
    html = html_of(message)
    assert "<strong>Note:</strong> Next week." in html
    assert f'<a href="{link}">Open the request</a>' in html
    assert FOOTER in html


EMAILING_MOVES = [
    # from, to, note, subject, sentence, label
    ("submitted", "rejected", "Too big.", "Your print request was rejected", "was rejected."),
    (
        "approved",
        "waiting_on_filament",
        "",
        "Your print request is waiting on filament",
        "is waiting on filament.",
    ),
    ("queued", "printing", "", "Your print request is printing", "is printing."),
    ("printing", "done", "Came out well.", "Your print is done", "is done."),
    ("printing", "failed", "Spaghetti at layer 40.", "Your print failed", "failed."),
    *(
        (status, "cancelled", "Out of filament.", "Your print request was cancelled", "cancelled.")
        for status in ("submitted", "approved", "waiting_on_filament", "queued", "failed")
    ),
]


@pytest.mark.parametrize(("from_status", "to_status", "note", "subject", "ending"), EMAILING_MOVES)
def test_the_requester_is_emailed_for_each_move_that_emails_them(
    app: FastAPI,
    frank: TestClient,
    outbox: FakeOutbox,
    db: Session,
    request_id: int,
    from_status: str,
    to_status: str,
    note: str,
    subject: str,
    ending: str,
) -> None:
    _in(db, request_id, from_status)

    response = move(frank, request_id, from_status, to_status, note)

    assert response.status_code == 200, response.text
    message = _one(app, outbox)
    assert message["To"] == "sam@example.com"
    assert message["Subject"] == f"{subject}: {TITLE}"
    text = text_of(message)
    first, *_ = text.split("\n")
    assert first.startswith("Your print") and first.endswith(ending)
    assert f'"{TITLE}"' in first
    if note:
        assert f"\n\n{'Note' if to_status in ('done', 'failed') else 'Reason'}: {note}\n" in text
    assert f"Open the request: https://rollcall.example.com/requests/{request_id}" in text
    assert text.endswith(f"{FOOTER}\n")


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        ("approved", "queued"),
        ("waiting_on_filament", "queued"),
        ("failed", "queued"),  # Reprint
        ("done", "picked_up"),
    ],
)
def test_no_email_for_queued_reprint_or_an_admin_picking_up(
    app: FastAPI,
    frank: TestClient,
    outbox: FakeOutbox,
    db: Session,
    request_id: int,
    from_status: str,
    to_status: str,
) -> None:
    _in(db, request_id, from_status)

    assert move(frank, request_id, from_status, to_status).status_code == 200

    assert sent(app, outbox) == []


@pytest.mark.parametrize(
    ("from_status", "to_status"), [("queued", "cancelled"), ("done", "picked_up")]
)
def test_no_email_for_the_requesters_own_moves(
    app: FastAPI,
    sam: TestClient,
    outbox: FakeOutbox,
    db: Session,
    request_id: int,
    from_status: str,
    to_status: str,
) -> None:
    _in(db, request_id, from_status)

    assert move(sam, request_id, from_status, to_status, "Changed my mind.").status_code == 200

    assert sent(app, outbox) == []


def test_no_email_when_an_admin_cancels_their_own_request(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    boss = person(app, "boss", Role.ADMIN)
    boss.patch("/api/v1/auth/me", json={"email": "boss@example.com"}, headers=CSRF)
    request_id = submitted(boss)["id"]
    sent(app, outbox)

    assert move(boss, request_id, "submitted", "cancelled").status_code == 200

    assert sent(app, outbox) == []


def test_no_email_for_edits_or_priority_changes(
    app: FastAPI, sam: TestClient, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    assert edit(sam, request_id, title="Lamp shade, smaller").status_code == 200
    priority = frank.post(
        f"{REQUESTS}/{request_id}/priority", json={"priority": "urgent"}, headers=CSRF
    )
    assert priority.status_code == 200

    assert sent(app, outbox) == []


def test_no_email_to_a_requester_with_no_address(
    app: FastAPI, sam: TestClient, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    sam.patch("/api/v1/auth/me", json={"email": ""}, headers=CSRF)

    assert move(frank, request_id, "submitted", "approved").status_code == 200

    assert sent(app, outbox) == []


def test_no_email_to_a_requester_whose_switch_is_off(
    app: FastAPI, sam: TestClient, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    sam.patch("/api/v1/auth/me", json={"email_on_request_change": False}, headers=CSRF)

    assert move(frank, request_id, "submitted", "approved").status_code == 200

    assert sent(app, outbox) == []


def test_no_email_to_a_disabled_requester(
    app: FastAPI,
    client: TestClient,
    sam: TestClient,
    frank: TestClient,
    outbox: FakeOutbox,
    request_id: int,
) -> None:
    sam_id = sam.get("/api/v1/auth/me").json()["id"]
    client.patch(f"/api/v1/users/{sam_id}", json={"disabled": True}, headers=admin())

    assert move(frank, request_id, "submitted", "rejected", "Not now.").status_code == 200

    assert sent(app, outbox) == []


def test_no_email_while_email_is_off(
    app: FastAPI, client: TestClient, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    email_on(client, smtp_host="")

    assert move(frank, request_id, "submitted", "approved").status_code == 200

    email_on(client)  # So the check below can see what was sent.
    assert sent(app, outbox) == []


def test_no_link_without_a_public_url(
    app: FastAPI, client: TestClient, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    email_on(client, public_url="")

    response = frank.post(
        f"{REQUESTS}/{request_id}/moves",
        json={"from_status": "submitted", "to_status": "approved", "note": ""},
        headers={**CSRF, "Host": "evil.example.com"},
    )

    assert response.status_code == 200, response.text

    message = _one(app, outbox)
    for body in (text_of(message), html_of(message)):
        assert "Open the request" not in body
        assert "http" not in body
        assert "evil.example.com" not in body
    assert text_of(message) == f'Your print request "{TITLE}" was approved.\n\n{FOOTER}\n'


def test_the_title_and_note_are_escaped_in_the_html(
    app: FastAPI, sam: TestClient, frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    edit(sam, request_id, title="Gears <b>& bolts</b>")

    move(frank, request_id, "submitted", "rejected", "<script>alert(1)</script>")

    html = html_of(_one(app, outbox))
    assert "&quot;Gears &lt;b&gt;&amp; bolts&lt;/b&gt;&quot;" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>" not in html


def test_a_failing_transport_never_fails_a_move(
    frank: TestClient, outbox: FakeOutbox, request_id: int
) -> None:
    outbox.fail()

    response = move(frank, request_id, "submitted", "approved")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    deadline = time.monotonic() + 5
    while outbox.attempts == 0:
        assert time.monotonic() < deadline, "the email was never tried"
        time.sleep(0.005)
    assert outbox.sent == []
