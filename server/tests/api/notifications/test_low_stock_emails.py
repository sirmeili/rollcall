"""Low stock emails: everyone with an address who chose Low stock by email (off by default) is
emailed once each time a product goes from not low to low stock. The always-on database poll
notices it, Home Assistant or not; the tests make changes through the API and run the poll
between them."""

import threading

from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from email_helpers import email_on, notify, sent
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

API = "/api/v1"
ACCOUNT = f"{API}/auth/me"
FOOTER = "You can change these on your Account page."
LOW_STOCK_OFF = {"kind": "low_stock", "channel": "email", "on": False, "default": True}


def _person(app: FastAPI, username: str, role: Role = Role.VIEWER) -> TestClient:
    """A signed-in user with an address."""
    user = signed_in(app, role, username=username)
    user.patch(ACCOUNT, json={"email": f"{username}@example.com"}, headers=CSRF)
    return user


def _product(client: TestClient, name: str, sealed: int, threshold: int = 0) -> int:
    """A product with `sealed` Sealed spools and a low stock threshold; its ID."""
    body = {
        "display_name": name,
        "filament_type": "PLA",
        "color_rgba": "000000FF",
        "low_stock_threshold": threshold,
    }
    response = client.post(f"{API}/products", json=body, headers=admin())
    assert response.status_code == 201, response.text
    product_id = response.json()["id"]
    _sealed(client, product_id, sealed)
    return product_id


def _sealed(client: TestClient, product_id: int, count: int = 1) -> list[int]:
    """`count` more Sealed spools of the product; their IDs."""
    ids = []
    for _ in range(count):
        added = client.post(f"{API}/spools", json={"product_id": product_id}, headers=admin())
        assert added.status_code == 201, added.text
        ids.append(added.json()["id"])
    return ids


def _open(client: TestClient, spool_id: int) -> None:
    response = client.post(
        f"{API}/spools/{spool_id}/events", json={"action": "opened"}, headers=admin()
    )
    assert response.status_code == 200, response.text


def _threshold(client: TestClient, product_id: int, value: int) -> None:
    response = client.patch(
        f"{API}/products/{product_id}", json={"low_stock_threshold": value}, headers=admin()
    )
    assert response.status_code == 200, response.text


def _poll(app: FastAPI) -> None:
    """One run of the database poll, as the server makes every few seconds."""
    app.state.poll.step()


def test_everyone_can_choose_low_stock_and_it_is_off_by_default(
    app: FastAPI, client: TestClient
) -> None:
    for role in Role:
        me = signed_in(app, role).get(ACCOUNT).json()

        assert LOW_STOCK_OFF in me["notifications"], role


def test_one_email_when_a_raised_threshold_makes_a_product_low(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=2)
    _poll(app)

    _threshold(client, black, 2)
    _poll(app)

    [message] = sent(app, outbox)
    assert message["To"] == "sam@example.com"
    assert message["Subject"] == "Low stock: Black PLA Basic"
    link = "https://rollcall.example.com/?q=Black%20PLA%20Basic"
    assert text_of(message) == (
        f"Black PLA Basic is low: 2 Sealed spools left.\n\nOpen Inventory: {link}\n\n{FOOTER}\n"
    )
    assert f'<a href="{link}">Open Inventory</a>' in html_of(message)


def test_once_per_change_into_low_stock(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=0, threshold=1)
    first, second, third = _sealed(client, black, 3)
    _poll(app)

    _open(client, first)
    _poll(app)
    assert sent(app, outbox) == []  # 2 Sealed left: not low yet

    _open(client, second)
    _poll(app)
    [message] = sent(app, outbox)
    assert text_of(message).startswith("Black PLA Basic is low: 1 Sealed spools left.")

    _open(client, third)
    _poll(app)
    assert sent(app, outbox) == []  # still low: not again

    _sealed(client, black, 2)
    _poll(app)
    assert sent(app, outbox) == []  # no longer low
    _threshold(client, black, 2)
    _poll(app)
    assert [m["Subject"] for m in sent(app, outbox)] == ["Low stock: Black PLA Basic"]


def test_nothing_when_a_threshold_is_lowered_or_turned_off(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=1, threshold=3)
    white = _product(client, "White PLA Basic", sealed=1, threshold=3)
    _poll(app)
    assert len(sent(app, outbox)) == 2  # both went low after the server started

    _threshold(client, black, 0)
    _threshold(client, white, 1)
    _poll(app)
    _threshold(client, white, 0)
    _poll(app)

    assert sent(app, outbox) == []


def test_nothing_on_the_first_poll_after_a_restart(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, db_url: str
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=2)
    _poll(app)
    _threshold(client, black, 2)  # goes low while the server is down: nobody is told

    restarted = create_app(
        Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None),
        mail_transport=outbox,
    )
    with TestClient(restarted, base_url=BASE_URL, client=LAN_CLIENT):
        _poll(restarted)
        _poll(restarted)

        assert sent(restarted, outbox) == []


def test_each_product_and_each_person_gets_their_own_email(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    for name, role in (("sam", Role.VIEWER), ("eve", Role.EDITOR), ("frank", Role.ADMIN)):
        notify(_person(app, name, role), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=1)
    white = _product(client, "White PLA Basic", sealed=1)
    _poll(app)

    _threshold(client, black, 1)
    _threshold(client, white, 1)
    _poll(app)

    assert sorted((m["To"], m["Subject"]) for m in sent(app, outbox)) == [
        (f"{name}@example.com", f"Low stock: {product}")
        for name in ("eve", "frank", "sam")
        for product in ("Black PLA Basic", "White PLA Basic")
    ]


def test_only_those_who_chose_it_with_an_address_and_an_enabled_account(
    app: FastAPI, client: TestClient, outbox: FakeOutbox
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "low_stock", True)
    _person(app, "mia")  # left at the default: off
    notify(_person(app, "ann"), "low_stock", False)
    nobody = signed_in(app, Role.VIEWER, username="nobody")  # no address
    notify(nobody, "low_stock", True)
    gone = _person(app, "gone")
    notify(gone, "low_stock", True)
    gone_id = gone.get(ACCOUNT).json()["id"]
    client.patch(f"{API}/users/{gone_id}", json={"disabled": True}, headers=admin())
    black = _product(client, "Black PLA Basic", sealed=1)
    _poll(app)

    _threshold(client, black, 1)
    _poll(app)

    assert [m["To"] for m in sent(app, outbox)] == ["sam@example.com"]


def test_no_link_without_a_public_url(app: FastAPI, client: TestClient, outbox: FakeOutbox) -> None:
    email_on(client, public_url="")
    notify(_person(app, "sam"), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=1)
    _poll(app)

    _threshold(client, black, 1)
    _poll(app)

    [message] = sent(app, outbox)
    assert text_of(message) == f"Black PLA Basic is low: 1 Sealed spools left.\n\n{FOOTER}\n"
    assert "http" not in html_of(message)


def test_nothing_while_email_is_off(app: FastAPI, client: TestClient, outbox: FakeOutbox) -> None:
    notify(_person(app, "sam"), "low_stock", True)
    black = _product(client, "Black PLA Basic", sealed=1)
    _poll(app)

    _threshold(client, black, 1)
    _poll(app)

    email_on(client)  # So the check below can see what was sent.
    assert sent(app, outbox) == []


def test_the_poll_runs_without_home_assistant(app: FastAPI, client: TestClient) -> None:
    assert app.state.home_assistant.sender.rest is None

    assert any(thread.name == "poll" for thread in threading.enumerate())
