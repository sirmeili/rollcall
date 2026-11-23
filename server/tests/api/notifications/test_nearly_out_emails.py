"""Nearly out emails: everyone with an address who chose Nearly out by email (off by default)
is emailed once each time a spool goes from not nearly out to nearly out: Open, in an AMS, at
or below its product's cutoff. The tests feed AMS reports and run the poll between them."""

from datetime import UTC, datetime

from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from email_helpers import email_on, notify, sent
from fake_outbox import FakeOutbox, html_of, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.config import Settings
from filament_tracker.db.models import Printer, Spool
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.ams import ingest

API = "/api/v1"
ACCOUNT = f"{API}/auth/me"
FOOTER = "You can change these on your Account page."
NEARLY_OUT_OFF = {"kind": "nearly_out", "channel": "email", "on": False, "default": True}
BLACK = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
WHITE = "0F1E2D3C4B5A69788796A5B4C3D2E1F0"
COLORS = {BLACK: ("000000FF", "Black PLA Basic"), WHITE: ("FFFFFFFF", "White PLA Basic")}
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def _person(app: FastAPI, username: str, role: Role = Role.VIEWER) -> TestClient:
    """A signed-in user with an address."""
    user = signed_in(app, role, username=username)
    user.patch(ACCOUNT, json={"email": f"{username}@example.com"}, headers=CSRF)
    return user


def _tray(slot: int, uid: str, pct: int) -> TrayReport:
    """A spool in slot `slot` (0-based) of the first AMS, at `pct` remaining."""
    return TrayReport(0, slot, uid, "GFA00", "PLA", "PLA Basic", COLORS[uid][0], pct)


def _ams(session: Session, client: TestClient, *trays: TrayReport, printer: str = "P1S") -> None:
    """The printer's AMS reports the trays (and nothing else loaded). A spool seen for the
    first time gets its product's name, as someone would after the AMS made it."""
    found = session.scalar(select(Printer).where(Printer.name == printer))
    if found is None:
        found = Printer(name=printer, serial=f"01P00A00000{printer}", host="192.168.1.40")
        session.add(found)
    ingest(session, found, list(trays), T0)
    session.commit()
    for tray in (t for t in trays if t.tray_uuid is not None):
        product = _spool(session, tray.tray_uuid).product
        name = COLORS[tray.tray_uuid][1]
        if product.display_name != name:
            response = client.patch(
                f"{API}/products/{product.id}", json={"display_name": name}, headers=admin()
            )
            assert response.status_code == 200, response.text


def _spool(session: Session, uid: str) -> Spool:
    session.expire_all()
    spool = session.scalar(select(Spool).where(Spool.tray_uid == uid))
    assert spool is not None
    return spool


def _poll(app: FastAPI) -> None:
    """One run of the database poll, as the server makes every few seconds."""
    app.state.poll.step()


def _started(app: FastAPI, outbox: FakeOutbox) -> None:
    """The first poll: it only records where things stand. The server's own poll may have
    looked first, so whatever that sent is cleared."""
    _poll(app)
    sent(app, outbox)


def test_everyone_can_choose_nearly_out_and_it_is_off_by_default(
    app: FastAPI, client: TestClient
) -> None:
    for role in Role:
        me = signed_in(app, role).get(ACCOUNT).json()

        assert NEARLY_OUT_OFF in me["notifications"], role


def test_one_email_when_a_spool_in_the_ams_becomes_nearly_out(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "nearly_out", True)
    _ams(session, client, _tray(1, BLACK, 60))
    _started(app, outbox)

    _ams(session, client, _tray(1, BLACK, 15))
    _poll(app)

    [message] = sent(app, outbox)
    spool_id = _spool(session, BLACK).id
    assert message["To"] == "sam@example.com"
    assert message["Subject"] == "Nearly out: Black PLA Basic in AMS 1, slot 2 on P1S"
    link = f"https://rollcall.example.com/spools/{spool_id}"
    assert text_of(message) == (
        "Black PLA Basic in AMS 1, slot 2 on P1S has about 15% left.\n\n"
        f"Open the spool: {link}\n\n{FOOTER}\n"
    )
    assert f'<a href="{link}">Open the spool</a>' in html_of(message)


def test_nothing_while_it_stays_nearly_out_and_again_after_it_rises_above_the_cutoff(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "nearly_out", True)
    _ams(session, client, _tray(0, BLACK, 40))
    _started(app, outbox)

    _ams(session, client, _tray(0, BLACK, 12))
    _poll(app)
    assert len(sent(app, outbox)) == 1

    _ams(session, client, _tray(0, BLACK, 8))
    _poll(app)
    assert sent(app, outbox) == []  # still nearly out: not again

    _ams(session, client, _tray(0, BLACK, 16))  # above the 15% cutoff: re-armed
    _poll(app)
    assert sent(app, outbox) == []
    _ams(session, client, _tray(0, BLACK, 14))
    _poll(app)
    [message] = sent(app, outbox)
    assert text_of(message).startswith("Black PLA Basic in AMS 1, slot 1 on P1S has about 14%")


def test_leaving_the_ams_re_arms_it(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "nearly_out", True)
    _ams(session, client, _tray(0, BLACK, 10))
    _started(app, outbox)

    _ams(session, client, TrayReport(0, 0))  # taken out: its remaining % stays on the spool
    _poll(app)
    assert sent(app, outbox) == []

    _ams(session, client, _tray(2, BLACK, 10))  # loaded again, in another slot
    _poll(app)
    [message] = sent(app, outbox)
    assert message["Subject"] == "Nearly out: Black PLA Basic in AMS 1, slot 3 on P1S"


def test_nothing_on_the_first_poll_after_a_restart(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session, db_url: str
) -> None:
    email_on(client)
    notify(_person(app, "sam"), "nearly_out", True)
    _ams(session, client, _tray(0, BLACK, 60))
    _started(app, outbox)
    _ams(session, client, _tray(0, BLACK, 10))  # nearly out while the server is down

    restarted = create_app(
        Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None),
        mail_transport=outbox,
    )
    with TestClient(restarted, base_url=BASE_URL, client=LAN_CLIENT):
        _poll(restarted)
        _poll(restarted)

        assert sent(restarted, outbox) == []


def test_each_spool_and_each_person_gets_their_own_email(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session
) -> None:
    email_on(client)
    for name, role in (("sam", Role.VIEWER), ("eve", Role.EDITOR)):
        notify(_person(app, name, role), "nearly_out", True)
    _person(app, "mia")  # left at the default: off
    _ams(session, client, _tray(0, BLACK, 50))
    _ams(session, client, _tray(3, WHITE, 50), printer="X1C")
    _started(app, outbox)

    _ams(session, client, _tray(0, BLACK, 5))
    _ams(session, client, _tray(3, WHITE, 15), printer="X1C")
    _poll(app)

    assert sorted((m["To"], m["Subject"]) for m in sent(app, outbox)) == [
        (f"{name}@example.com", subject)
        for name in ("eve", "sam")
        for subject in (
            "Nearly out: Black PLA Basic in AMS 1, slot 1 on P1S",
            "Nearly out: White PLA Basic in AMS 1, slot 4 on X1C",
        )
    ]


def test_no_link_without_a_public_url(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session
) -> None:
    email_on(client, public_url="")
    notify(_person(app, "sam"), "nearly_out", True)
    _ams(session, client, _tray(0, BLACK, 50))
    _started(app, outbox)

    _ams(session, client, _tray(0, BLACK, 15))
    _poll(app)

    [message] = sent(app, outbox)
    assert text_of(message) == (
        f"Black PLA Basic in AMS 1, slot 1 on P1S has about 15% left.\n\n{FOOTER}\n"
    )
    assert "http" not in html_of(message)


def test_nothing_while_email_is_off(
    app: FastAPI, client: TestClient, outbox: FakeOutbox, session: Session
) -> None:
    notify(_person(app, "sam"), "nearly_out", True)
    _ams(session, client, _tray(0, BLACK, 50))
    _poll(app)

    _ams(session, client, _tray(0, BLACK, 15))
    _poll(app)

    email_on(client)  # So the check below can see what was sent.
    assert sent(app, outbox) == []
