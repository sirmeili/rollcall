"""Phone notifications: everyone the notification resolver tells about a kind by Phone gets a
Web Push on each of their registered phones, encrypted for that phone and signed with the
server's VAPID key, carrying the kind, the email's subject and sentence, and the page's path.
Never about what they did themselves, nor for a disabled user; sent in the background, whether
or not email is set up."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from email_helpers import email_on
from fake_push_outbox import FakePushOutbox, vapid_claims
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phone_helpers import CONFIG, pushed, to, users_phone
from request_helpers import person, submitted
from sqlalchemy import select
from test_photos import add_photos, jpeg, move, printing, uploaded_photo

from filament_tracker.config import Settings
from filament_tracker.db.models import Printer
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app
from filament_tracker.notifications.notification import Notification
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.ams import ingest

API = "/api/v1"
ACCOUNT = f"{API}/auth/me"
TITLE = "Lithophane lamp shade"


def _phone_off(user: TestClient, kind: str) -> None:
    response = user.patch(
        ACCOUNT,
        json={"notifications": [{"kind": kind, "channel": "phone", "on": False}]},
        headers=CSRF,
    )
    assert response.status_code == 200, response.text


def test_an_admin_hears_of_a_new_request_on_their_phone(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    phone = users_phone(frank)
    sam = person(app, "sam")

    request_id = submitted(sam, title=TITLE)["id"]

    [message] = pushed(app, pushes)
    assert phone.decrypt(message) == {
        "kind": "new_request",
        "title": f"New print request from sam: {TITLE}",
        "text": f'sam submitted a new print request: "{TITLE}".',
        "path": f"/requests/{request_id}",
    }
    assert message.endpoint == phone.endpoint
    claims = vapid_claims(message, frank.get(CONFIG).json()["vapid_public_key"])
    assert claims["sub"].startswith("mailto:")
    assert claims["exp"] > datetime.now(UTC).timestamp()
    assert message.headers["TTL"] == str(7 * 24 * 3600)
    assert message.headers["Urgency"] == "normal"
    assert message.headers["Content-Type"] == "application/octet-stream"
    assert len(message.body) < 4096


def test_each_registered_phone_of_each_person_told_gets_it(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    franks = [users_phone(frank, f"https://push.example.com/frank{n}") for n in (1, 2)]
    eddie = person(app, "eddie", Role.EDITOR, requester=False)
    eddies = users_phone(eddie, "https://push.example.com/eddie")
    person(app, "nophone", Role.ADMIN, requester=False)

    submitted(person(app, "sam"), title=TITLE)

    messages = pushed(app, pushes)
    assert sorted(m.endpoint for m in messages) == sorted(
        [franks[0].endpoint, franks[1].endpoint, eddies.endpoint]
    )
    for phone in (*franks, eddies):
        assert [p["kind"] for p in to(phone, messages)] == ["new_request"]


def test_nobody_hears_of_what_they_did_themselves(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    boss = person(app, "boss", Role.ADMIN, requester=True)
    users_phone(boss)

    submitted(boss, title=TITLE)

    assert pushed(app, pushes) == []


def test_a_kind_turned_off_for_phone_isnt_sent_to_the_phone(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    users_phone(frank)
    _phone_off(frank, "new_request")

    submitted(person(app, "sam"), title=TITLE)

    assert pushed(app, pushes) == []


def test_a_disabled_user_gets_none(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    users_phone(frank)
    person(app, "boss", Role.ADMIN, requester=False)
    frank_id = frank.get(ACCOUNT).json()["id"]
    disabled = client.patch(f"{API}/users/{frank_id}", json={"disabled": True}, headers=admin())
    assert disabled.status_code == 200, disabled.text

    submitted(person(app, "sam"), title=TITLE)

    assert pushed(app, pushes) == []


def test_phones_hear_whether_or_not_email_is_set_up(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    phone = users_phone(frank)
    sam = person(app, "sam")

    submitted(sam, title="Before email")
    email_on(client)
    submitted(sam, title="After email")

    titles = [p["title"] for p in to(phone, pushed(app, pushes))]
    assert sorted(titles) == [
        "New print request from sam: After email",
        "New print request from sam: Before email",
    ]


def test_a_requester_hears_of_their_request_moving_and_new_photos(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    sam = person(app, "sam")
    phone = users_phone(sam)
    frank = person(app, "frank", Role.ADMIN, requester=False)
    request_id = printing(sam, frank)
    pushed(app, pushes)

    assert move(frank, request_id, "printing", "done").status_code == 200
    photo_id = uploaded_photo(frank, jpeg((60, 40)))
    assert add_photos(frank, request_id, photo_id).status_code == 200

    path = f"/requests/{request_id}"
    assert to(phone, pushed(app, pushes)) == [
        {
            "kind": "request_update",
            "title": "Your print is done: Lithophane lamp shade",
            "text": 'Your print "Lithophane lamp shade" is done.',
            "path": path,
        },
        {
            "kind": "new_photo",
            "title": "New photo of your print: Lithophane lamp shade",
            "text": 'A new photo of your print "Lithophane lamp shade" was added.',
            "path": path,
            "photo": f"{API}/requests/{request_id}/photos/{photo_id}",
        },
    ]


def test_done_and_new_photo_name_the_first_photo_for_the_phone_to_show(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    sam = person(app, "sam")
    phone = users_phone(sam)
    frank = person(app, "frank", Role.ADMIN, requester=False)
    request_id = printing(sam, frank)
    pushed(app, pushes)
    first, second = uploaded_photo(frank, jpeg((60, 40))), uploaded_photo(frank, jpeg())

    assert move(frank, request_id, "printing", "done", photo_ids=[first, second]).status_code == 200
    third, fourth = uploaded_photo(frank, jpeg()), uploaded_photo(frank, jpeg())
    assert add_photos(frank, request_id, third, fourth).status_code == 200

    done, new_photo = to(phone, pushed(app, pushes))
    photos = f"{API}/requests/{request_id}/photos"
    assert (done["kind"], done["photo"]) == ("request_update", f"{photos}/{first}")
    assert (new_photo["kind"], new_photo["photo"]) == ("new_photo", f"{photos}/{third}")


def test_only_someone_who_may_see_the_request_downloads_the_named_photo(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    sam = person(app, "sam")
    phone = users_phone(sam)
    frank = person(app, "frank", Role.ADMIN, requester=False)
    request_id = printing(sam, frank)
    pushed(app, pushes)
    photo_id = uploaded_photo(frank, jpeg())
    assert move(frank, request_id, "printing", "done", photo_ids=[photo_id]).status_code == 200

    [done] = to(phone, pushed(app, pushes))
    maya = person(app, "maya")

    assert sam.get(done["photo"]).headers["Content-Type"] == "image/jpeg"
    assert maya.get(done["photo"]).status_code == 404


def test_a_move_other_than_done_with_photos_names_no_photo(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    sam = person(app, "sam")
    phone = users_phone(sam)
    frank = person(app, "frank", Role.ADMIN, requester=False)
    request_id = printing(sam, frank)
    pushed(app, pushes)

    assert move(frank, request_id, "printing", "failed", note="Spaghetti").status_code == 200

    [failed] = to(phone, pushed(app, pushes))
    assert failed["kind"] == "request_update"
    assert "photo" not in failed


def test_editors_hear_of_a_suggestion_but_not_the_suggester(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    eddie = signed_in(app, Role.EDITOR, username="eddie")
    phone = users_phone(eddie)
    product = _product(client, "Black PLA Basic", sealed=3)

    response = eddie.post(
        f"{API}/shopping-list/suggestions", json={"product_id": product, "spools": 2}, headers=CSRF
    )
    assert response.status_code == 200, response.text
    assert pushed(app, pushes) == []

    viewer = signed_in(app, Role.VIEWER, username="vera")
    viewer.post(
        f"{API}/shopping-list/suggestions", json={"product_id": product, "spools": 1}, headers=CSRF
    )

    assert to(phone, pushed(app, pushes)) == [
        {
            "kind": "suggestion",
            "title": "New suggestion from vera: Black PLA Basic",
            "text": "vera suggested 1 spool of Black PLA Basic for the shopping list.",
            "path": "/shopping-list",
        }
    ]


def _product(client: TestClient, name: str, sealed: int, threshold: int = 0) -> int:
    body = {
        "display_name": name,
        "filament_type": "PLA",
        "color_rgba": "000000FF",
        "low_stock_threshold": threshold,
    }
    response = client.post(f"{API}/products", json=body, headers=admin())
    assert response.status_code == 201, response.text
    product_id = response.json()["id"]
    for _ in range(sealed):
        added = client.post(f"{API}/spools", json={"product_id": product_id}, headers=admin())
        assert added.status_code == 201, added.text
    return product_id


def test_everyone_hears_of_low_stock_on_their_phone_by_default(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    vera = signed_in(app, Role.VIEWER, username="vera")
    phone = users_phone(vera)
    product = _product(client, "Black PLA Basic", sealed=3, threshold=1)
    app.state.poll.step()
    pushed(app, pushes)

    response = client.patch(
        f"{API}/products/{product}", json={"low_stock_threshold": 3}, headers=admin()
    )
    assert response.status_code == 200
    app.state.poll.step()

    assert to(phone, pushed(app, pushes)) == [
        {
            "kind": "low_stock",
            "title": "Low stock: Black PLA Basic",
            "text": "Black PLA Basic is low: 3 Sealed spools left.",
            "path": "/?q=Black%20PLA%20Basic",
        }
    ]


def test_everyone_hears_of_a_nearly_out_spool_on_their_phone(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    vera = signed_in(app, Role.VIEWER, username="vera")
    phone = users_phone(vera)
    uid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    when = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)

    def ams(pct: int) -> None:
        with app.state.session_factory() as session:
            printer = session.scalar(select(Printer)) or Printer(
                name="P1S", serial="01P00A000000001", host="192.168.1.40"
            )
            session.add(printer)
            tray = TrayReport(0, 0, uid, "GFA00", "PLA", "PLA Basic", "000000FF", pct)
            ingest(session, printer, [tray], when)
            session.commit()

    ams(80)
    app.state.poll.step()
    pushed(app, pushes)
    ams(5)
    app.state.poll.step()

    [payload] = to(phone, pushed(app, pushes))
    assert payload["kind"] == "nearly_out"
    assert payload["text"].endswith("has about 5% left.")
    assert payload["path"].startswith("/spools/")


def test_admins_hear_of_a_failed_backup_on_their_phone(
    db_url: str, tmp_path: Path, pushes: FakePushOutbox
) -> None:
    folder = tmp_path / "backups"
    folder.write_text("not a folder")
    settings = Settings(
        database_url=db_url, admin_token=ADMIN_TOKEN, backup_dir=folder, _env_file=None
    )
    app = create_app(settings, push_transport=pushes)
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT):
        frank = signed_in(app, Role.ADMIN, username="frank")
        phone = users_phone(frank)

        app.state.backups.run_once(datetime(2026, 11, 22, 3, 0, tzinfo=UTC))

        [payload] = to(phone, pushed(app, pushes))
    assert payload["kind"] == "backup_failed"
    assert payload["title"] == "Backup failed"
    assert payload["text"].startswith("Last night's backup failed: ")
    assert payload["path"] == "/settings"


def test_a_push_service_failing_never_fails_the_change(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    frank = person(app, "frank", Role.ADMIN, requester=False)
    users_phone(frank)
    pushes.answer(None, None, 503, 429)

    # It answers 201 as ever.
    submitted(person(app, "sam"), title=TITLE)


def test_a_gone_endpoint_is_dropped_at_once(
    app: FastAPI, client: TestClient, pushes: FakePushOutbox
) -> None:
    sam = person(app, "sam")
    frank = person(app, "frank", Role.ADMIN, requester=False)
    gone = users_phone(frank, "https://push.example.com/gone")

    for status in (404, 410):
        pushes.answer(status)
        submitted(sam, title=TITLE)
        assert pushed(app, pushes) == []
        attempts = pushes.attempts
        submitted(sam, title="Again")
        pushed(app, pushes)
        # Nothing more is tried for the dropped phone.
        assert pushes.attempts == attempts
        frank.put(f"{API}/push/devices/{gone.device_id}", json=gone.subscription(), headers=CSRF)


def test_a_notification_that_cant_be_built_is_logged_by_type_and_dropped(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    def build() -> list[Notification]:
        raise RuntimeError("secret detail")

    with app.state.session_factory() as session:
        app.state.notifier.send(session, build)

    assert "unexpected RuntimeError" in caplog.text
    assert "secret detail" not in caplog.text
