"""Photos in emails: the Done email carries the photos saved with the move, and a photo added
later emails the requester "New photo of your print", each photo an inline image in the HTML
part. Read through the fake outbox."""

import io
from email.message import EmailMessage

import pytest
from api_helpers import CSRF, admin
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from request_helpers import person
from test_photos import add_photos, jpeg, move, png, printing, remove_photo, uploaded_photo

from filament_tracker.domain.enums import Role

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
def printing_id(
    app: FastAPI, client: TestClient, sam: TestClient, frank: TestClient, outbox: FakeOutbox
) -> int:
    """Sam's request, moved on to Printing, with email set up and the emails so far sent."""
    email_on(client)
    request_id = printing(sam, frank)
    sent(app, outbox)
    return request_id


@pytest.fixture
def done_id(app: FastAPI, frank: TestClient, outbox: FakeOutbox, printing_id: int) -> int:
    """Sam's request, moved to Done with no photos, and its Done email sent."""
    assert move(frank, printing_id, "printing", "done").status_code == 200
    sent(app, outbox)
    return printing_id


def _one(app: FastAPI, outbox: FakeOutbox) -> EmailMessage:
    [message] = sent(app, outbox)
    return message


def inline_images(message: EmailMessage) -> list[tuple[str, Image.Image]]:
    """Each inline image in the message, with the Content-ID the HTML refers to it by."""
    found = []
    for part in message.walk():
        if part.get_content_maintype() != "image":
            continue
        assert part.get_content_type() == "image/jpeg"
        assert part.get_content_disposition() == "inline"
        content_id = str(part["Content-ID"]).strip("<>")
        image = Image.open(io.BytesIO(part.get_content()))
        image.load()
        found.append((content_id, image))
    return found


def test_the_done_email_shows_the_photos_saved_with_the_move_inline(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, printing_id: int
) -> None:
    ids = [uploaded_photo(frank, jpeg((2000, 1000))), uploaded_photo(frank, png((300, 600)))]

    response = move(frank, printing_id, "printing", "done", note="Came out well.", photo_ids=ids)

    assert response.status_code == 200, response.text
    message = _one(app, outbox)
    assert message["Subject"] == "Your print is done: Lithophane lamp shade"
    images = inline_images(message)
    # The email copies: JPEGs at most 1024 px on the long side, in the order they were added.
    assert [(image.format, image.size) for _, image in images] == [
        ("JPEG", (1024, 512)),
        ("JPEG", (300, 600)),
    ]
    html = html_of(message)
    for content_id, _ in images:
        assert f'src="cid:{content_id}"' in html
    assert text_of(message).endswith(f"{FOOTER}\n")


def test_a_done_email_without_photos_has_no_images(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, printing_id: int
) -> None:
    assert move(frank, printing_id, "printing", "done").status_code == 200

    message = _one(app, outbox)
    assert inline_images(message) == []
    assert "<img" not in html_of(message)


def test_a_photo_added_later_emails_the_requester_with_the_photo_inline(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    photo_id = uploaded_photo(frank, jpeg((1600, 1200)))

    assert add_photos(frank, done_id, photo_id).status_code == 200

    message = _one(app, outbox)
    assert message["To"] == "sam@example.com"
    assert message["Subject"] == f"New photo of your print: {TITLE}"
    link = f"https://rollcall.example.com/requests/{done_id}"
    assert text_of(message) == (
        f'A new photo of your print "{TITLE}" was added.\n\nOpen the request: {link}\n\n{FOOTER}\n'
    )
    [(content_id, image)] = inline_images(message)
    assert (image.format, image.size) == ("JPEG", (1024, 768))
    html = html_of(message)
    assert f'src="cid:{content_id}"' in html
    assert f'<a href="{link}">Open the request</a>' in html


def test_a_photo_added_after_pick_up_emails_the_requester(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    assert move(frank, done_id, "done", "picked_up").status_code == 200
    sent(app, outbox)

    assert add_photos(frank, done_id, uploaded_photo(frank, png())).status_code == 200

    message = _one(app, outbox)
    assert message["Subject"] == f"New photo of your print: {TITLE}"
    assert len(inline_images(message)) == 1


def test_photos_added_together_come_in_one_email(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    ids = [uploaded_photo(frank, jpeg()), uploaded_photo(frank, png())]

    assert add_photos(frank, done_id, *ids).status_code == 200

    assert len(inline_images(_one(app, outbox))) == 2


def test_removing_a_photo_sends_no_email(
    app: FastAPI, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    photo_id = uploaded_photo(frank, jpeg())
    add_photos(frank, done_id, photo_id)
    sent(app, outbox)

    assert remove_photo(frank, done_id, photo_id).status_code == 200

    assert sent(app, outbox) == []


def test_no_new_photo_email_to_a_requester_with_no_address(
    app: FastAPI, sam: TestClient, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    sam.patch("/api/v1/auth/me", json={"email": ""}, headers=CSRF)

    assert add_photos(frank, done_id, uploaded_photo(frank, jpeg())).status_code == 200

    assert sent(app, outbox) == []


def test_no_new_photo_email_to_a_requester_whose_switch_is_off(
    app: FastAPI, sam: TestClient, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    sam.patch("/api/v1/auth/me", json={"email_on_request_change": False}, headers=CSRF)

    assert add_photos(frank, done_id, uploaded_photo(frank, jpeg())).status_code == 200

    assert sent(app, outbox) == []


def test_no_new_photo_email_to_a_disabled_requester(
    app: FastAPI,
    client: TestClient,
    sam: TestClient,
    frank: TestClient,
    outbox: FakeOutbox,
    done_id: int,
) -> None:
    sam_id = sam.get("/api/v1/auth/me").json()["id"]
    client.patch(f"/api/v1/users/{sam_id}", json={"disabled": True}, headers=admin())

    assert add_photos(frank, done_id, uploaded_photo(frank, jpeg())).status_code == 200

    assert sent(app, outbox) == []


def test_no_new_photo_email_while_email_is_off(
    app: FastAPI, client: TestClient, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    email_on(client, smtp_host="")

    assert add_photos(frank, done_id, uploaded_photo(frank, jpeg())).status_code == 200

    email_on(client)  # So the check below can see what was sent.
    assert sent(app, outbox) == []


def test_no_new_photo_email_when_an_admin_adds_a_photo_to_their_own_request(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    boss = person(app, "boss", Role.ADMIN)
    boss.patch("/api/v1/auth/me", json={"email": "boss@example.com"}, headers=CSRF)
    request_id = printing(boss, boss)
    assert move(boss, request_id, "printing", "done").status_code == 200
    sent(app, outbox)

    assert add_photos(boss, request_id, uploaded_photo(boss, jpeg())).status_code == 200

    assert sent(app, outbox) == []


def test_no_link_in_the_new_photo_email_without_a_public_url(
    app: FastAPI, client: TestClient, frank: TestClient, outbox: FakeOutbox, done_id: int
) -> None:
    email_on(client, public_url="")

    assert add_photos(frank, done_id, uploaded_photo(frank, jpeg())).status_code == 200

    message = _one(app, outbox)
    assert text_of(message) == f'A new photo of your print "{TITLE}" was added.\n\n{FOOTER}\n'
    assert "Open the request" not in html_of(message)
