"""The upgrade from one image to another, as a test server does it (see docs/testing.md): the
previous image's data, backed up, restored and scrubbed by `prepare` in the test server's
stack (deploy/candidate/compose.yaml), then served by the new image.

Runs only when FT_COMPOSE_STACK is set (CI's image job sets it). ROLLCALL_IMAGE is the new
image (default `rollcall:test`) and PREVIOUS_IMAGE the one upgraded from (default the new
image). ROLLCALL_EXPECTED_VERSION is the version the new image was built to report (default
`dev`). Docker must be running.
"""

import base64
import os
import re
import secrets
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from compose_stacks import CSRF, DEPLOY, Stack, signed_in

from filament_tracker.simulator.cli import main as ft_sim

pytestmark = pytest.mark.skipif(
    not os.environ.get("FT_COMPOSE_STACK"), reason="set FT_COMPOSE_STACK to run the image"
)

NEW_IMAGE = os.environ.get("ROLLCALL_IMAGE", "rollcall:test")
PREVIOUS_IMAGE = os.environ.get("PREVIOUS_IMAGE", NEW_IMAGE)
EXPECTED_VERSION = os.environ.get("ROLLCALL_EXPECTED_VERSION", "dev")
ADMIN_TOKEN = "compose-test-admin-token-0123456789"  # noqa: S105 - deploy/test/compose.yaml's
ADMIN = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
PASSWORD = "correct horse battery"  # noqa: S105 - test value
CODE = re.compile(r"setup code: ([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})")
# Counts the test server's push registrations, in its database.
PUSH_REGISTRATIONS = (
    "import sqlite3; db = sqlite3.connect('file:/data/filament.db?mode=ro', uri=True);"
    " print(db.execute('SELECT count(*) FROM push_endpoint').fetchone()[0])"
)

# The previous image runs in the end-to-end stack, under its own project name and ports.
PREVIOUS = Stack(
    DEPLOY / "test" / "compose.yaml",
    "rollcall-upgrade-previous",
    18010,
    {"ROLLCALL_IMAGE": PREVIOUS_IMAGE, "TEST_PORT": "18010", "TEST_BROKER_PORT": "21893"},
)
# The test server's stack, reading the previous stack's backup volume as the live backups.
CANDIDATE = Stack(
    DEPLOY / "candidate" / "compose.yaml",
    "rollcall-upgrade-candidate",
    18011,
    {
        "CANDIDATE_IMAGE": NEW_IMAGE,
        "ROLLCALL_IMAGE": NEW_IMAGE,
        "LIVE_BACKUPS_VOLUME": "rollcall-upgrade-previous_backups",
        "CANDIDATE_PORT": "18011",
        "SETTINGS_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
        "TRUSTED_NETWORKS": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8",
        "COOKIE_SECURE": "false",
        "CATALOG_SYNC": "off",
        "TZ": "America/Chicago",
        "RESTORE": "1",
    },
)


@pytest.fixture(scope="module")
def stacks() -> Iterator[None]:
    CANDIDATE.compose("down", "--volumes", check=False)
    PREVIOUS.compose("down", "--volumes", check=False)
    try:
        yield
    finally:
        # Printed before the stacks go, so a failed test's report carries their logs.
        print(PREVIOUS.compose("logs", "--no-color", check=False))
        print(CANDIDATE.compose("logs", "--no-color", check=False))
        CANDIDATE.compose("down", "--volumes", check=False)
        PREVIOUS.compose("down", "--volumes", check=False)


def _created(response: httpx.Response) -> dict:
    assert response.status_code == 201, response.text
    return response.json()


def _saved(response: httpx.Response) -> None:
    assert response.status_code == 200, response.text


def _setting(browser: httpx.Client, group: str, key: str) -> dict:
    [found] = [s for s in browser.get(f"/settings/{group}").json()["settings"] if s["key"] == key]
    return found


def use_the_previous_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Data added through the previous image's API, and what it should keep and lose; its
    backup is in its backup volume. Returns the tokens it handed out."""
    PREVIOUS.up()
    http = httpx.Client(base_url=PREVIOUS.api, timeout=10, headers=ADMIN)
    [code] = CODE.findall(PREVIOUS.logs("rollcall"))
    setup = {"code": code, "username": "frank", "password": PASSWORD}
    _created(httpx.post(f"{PREVIOUS.api}/setup", json=setup, headers=CSRF))

    # An account that asks for prints.
    rita = {"username": "rita", "password": PASSWORD, "role": "viewer", "requester": True}
    _created(http.post("/users", json=rita))

    # A scanner, and a spool it receives and opens.
    scanner = _created(http.post("/devices", json={"id": "upgrade-sim", "name": "Upgrade test"}))
    monkeypatch.setenv("FT_TOKEN", scanner["token"])
    monkeypatch.setenv("FT_DEVICE_ID", "upgrade-sim")
    dump = tmp_path / "spool.bin"
    assert ft_sim(["generate", str(dump)]) == 0
    server = PREVIOUS.api.removesuffix("/api/v1")
    for action in ("received", "opened"):
        assert ft_sim(["scan", str(dump), "--action", action, "--server", server]) == 0
    [product] = http.get("/products").json()

    # Rita's print request, and her phone, registered for phone notifications.
    browser = signed_in(PREVIOUS, "rita", PASSWORD)
    choice = {"product_id": product["id"], "note": ""}
    request = {
        "title": "Upgrade test lamp shade",
        "notes": "",
        "quantity": 1,
        "needed_by": None,
        "priority": "normal",
        "link": "https://makerworld.com/en/models/412877",
        "choices": [choice],
    }
    _created(browser.post("/requests", json=request))
    phone = _created(browser.post("/devices/mine", json={"name": "Rita's phone"}))
    fcm = {"route": "fcm", "endpoint": "upgrade-test-fcm-token"}
    _saved(browser.put(f"/push/devices/{phone['id']}", json=fcm))

    # A machine token, a printer, and email, Home Assistant and Firebase settings.
    token = _created(http.post("/tokens", json={"name": "Home Assistant", "role": "viewer"}))
    printer = {
        "name": "P1S",
        "host": "192.0.2.40",
        "serial": "01P00A000000000",
        "access_code": "12345678",
    }
    _created(http.post("/printers", json=printer))
    email = {"smtp_host": "smtp.example.com", "smtp_from": "RollCall <rollcall@example.com>"}
    _saved(http.put("/settings/email", json={"values": email}))
    ha = {"mqtt_url": "mqtt://broker:1883", "ha_url": "http://192.0.2.10:8123"}
    _saved(http.put("/settings/home-assistant", json={"values": ha}))
    firebase = {"firebase_project_id": "rollcall-upgrade"}
    _saved(http.put("/settings/phone-notifications", json={"values": firebase}))

    # The backup the test server restores, then the previous image stops.
    assert "backup written: /backups/filament-" in PREVIOUS.run_in("rollcall", "ft-admin", "backup")
    PREVIOUS.compose("stop")
    return {"scanner": scanner["token"], "machine": token["token"], "phone": phone["token"]}


def test_the_new_image_upgrades_the_previous_images_data(
    stacks: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tokens = use_the_previous_image(tmp_path, monkeypatch)

    # prepare restores the backup with the new image, then the new image serves it.
    CANDIDATE.up("candidate")
    assert "restored filament-" in CANDIDATE.logs("prepare")
    assert httpx.get(f"{CANDIDATE.api}/health").json()["version"] == EXPECTED_VERSION

    # The data added on the previous image is all there, and setup stays closed.
    assert httpx.get(f"{CANDIDATE.api}/setup").json()["open"] is False
    frank = signed_in(CANDIDATE, "frank", PASSWORD)
    assert sorted(u["username"] for u in frank.get("/users").json()) == ["frank", "rita"]
    spools = frank.get("/spools").json()
    assert spools["total"] == 1
    assert spools["items"][0]["state"] == "open"
    assert [r["title"] for r in frank.get("/requests").json()] == ["Upgrade test lamp shade"]
    assert _setting(frank, "phone-notifications", "firebase_project_id")["value"] == (
        "rollcall-upgrade"
    )

    # Nothing it holds can reach the household: no device or machine token works, no phone
    # is registered, and email, Home Assistant and printers are off.
    devices = frank.get("/devices").json()
    assert [(d["id"], d["revoked"]) for d in devices] == [("upgrade-sim", True)]
    for token in tokens.values():
        refused = httpx.get(f"{CANDIDATE.api}/spools", headers={"Authorization": f"Bearer {token}"})
        assert refused.status_code == 401
    assert frank.get("/tokens").json() == []
    assert CANDIDATE.run_in("candidate", "python", "-c", PUSH_REGISTRATIONS).strip() == "0"
    assert frank.get("/printers").json() == []
    for group, key in [
        ("email", "smtp_host"),
        ("email", "smtp_from"),
        ("home-assistant", "mqtt_url"),
        ("home-assistant", "ha_url"),
    ]:
        assert _setting(frank, group, key)["set"] is False, key

    # The server runs without BACKUP_DIR, so it makes no backups.
    environ = CANDIDATE.run_in(
        "candidate", "python", "-c", "print('BACKUP_DIR=' in open('/proc/1/environ').read())"
    )
    assert environ.strip() == "False"

    # With RESTORE=0, prepare changes nothing: a scanner added after the upgrade stays.
    _created(frank.post("/devices", json={"id": "after-upgrade", "name": "After the upgrade"}))
    CANDIDATE.env["RESTORE"] = "0"
    CANDIDATE.up("candidate")
    assert "RESTORE is not 1" in CANDIDATE.logs("prepare")
    frank = signed_in(CANDIDATE, "frank", PASSWORD)
    assert [d["id"] for d in frank.get("/devices").json()] == ["after-upgrade", "upgrade-sim"]
