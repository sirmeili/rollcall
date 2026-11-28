"""`ft-admin restore --for-test`: a test server's copy of the newest live backup, scrubbed so
it can't reach the household."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from filament_tracker.admin_cli import main
from filament_tracker.config import Settings
from filament_tracker.db.migrate import upgrade

NOW = "2026-11-20 08:00:00.000000"


def _db(path: Path, template: Path) -> Path:
    """A migrated database at path, copied from the session's template."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, path)
    return path


def _run(path: Path, sql: str, *params: object) -> None:
    with sqlite3.connect(path) as db:
        db.execute(sql, params)
    db.close()


def _rows(path: Path, sql: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as db:
        rows = db.execute(sql).fetchall()
    db.close()
    return rows


def _add_user(path: Path, username: str) -> None:
    _run(
        path,
        "INSERT INTO user (username, password_hash, role, password_changed_at, created_at)"
        " VALUES (?, 'hash', 'admin', ?, ?)",
        username,
        NOW,
        NOW,
    )


def _usernames(path: Path) -> list[str]:
    return [name for (name,) in _rows(path, "SELECT username FROM user ORDER BY username")]


@pytest.fixture
def backups(tmp_path: Path) -> Path:
    folder = tmp_path / "backups"
    folder.mkdir()
    return folder


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return tmp_path / "data" / "filament.db"


@pytest.fixture
def settings(target: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{target}", _env_file=None)


def test_refuses_when_the_backups_directory_has_no_backup(
    backups: Path, target: Path, settings: Settings, capsys
) -> None:
    (backups / "notes.txt").write_text("not a backup", encoding="utf-8")

    code = main(["restore", "--for-test", str(backups)], settings=settings)

    assert code == 1
    assert f"no backup in {backups}" in capsys.readouterr().err
    assert not target.exists()


def test_restores_the_newest_of_several_backups_over_the_database(
    backups: Path, target: Path, settings: Settings, migrated_template: Path, capsys
) -> None:
    for name in (
        "filament-20261118T080000Z.db",
        "filament-20261120T080000Z.db",
        "filament-20261119T080000Z.db",
    ):
        _add_user(_db(backups / name, migrated_template), name[9:17])
    _add_user(_db(target, migrated_template), "replaced")

    code = main(["restore", "--for-test", str(backups)], settings=settings)

    assert code == 0
    assert _usernames(target) == ["20261120"]
    assert "restored filament-20261120T080000Z.db" in capsys.readouterr().out
    assert len(list(backups.iterdir())) == 3


SCRUBBED_SETTINGS = (
    "smtp_host",
    "smtp_port",
    "smtp_security",
    "smtp_user",
    "smtp_password",
    "smtp_from",
    "mqtt_url",
    "mqtt_user",
    "mqtt_password",
    "ha_url",
    "ha_token",
)
KEPT_SETTINGS = (
    "firebase_project_id",
    "firebase_app_id",
    "firebase_api_key",
    "firebase_sender_id",
    "firebase_service_account",
    "tz",
    "ha_discovery_prefix",
    "public_url",
)
KEPT_TABLES = ("user", "product", "spool", "event", "print_request")
SCANNER_TOKEN = "scanner-token-hash"  # noqa: S105 - test value
PHONE_TOKEN = "phone-token-hash"  # noqa: S105 - test value


def _add_live_data(path: Path) -> None:
    """What a live server holds: an account, a linked product with a spool scanned by one
    device, a second device with no history, a print request, a printer, a machine token,
    push registrations and settings."""
    _add_user(path, "frank")
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO product (id, filament_type, color_rgba, display_name,"
            " low_stock_threshold, provisional, created_at, catalog_manual_uuid)"
            " VALUES (1, 'PLA', '000000FF', 'Black PLA', 0, 0, ?, ?)",
            (NOW, "4f0c6c2e-0000-4000-8000-000000000001"),
        ),
        ("INSERT INTO spool (id, product_id, created_at) VALUES (1, 1, ?)", (NOW,)),
        (
            "INSERT INTO device (id, name, token_hash, created_at)"
            " VALUES ('scanner', 'Kitchen scanner', ?, ?), ('phone', 'Phone', ?, ?)",
            (SCANNER_TOKEN, NOW, PHONE_TOKEN, NOW),
        ),
        (
            "INSERT INTO event (id, spool_id, type, source, device_id, occurred_at,"
            " recorded_at, flagged) VALUES ('e1', 1, 'received', 'scanner', 'scanner', ?, ?, 0)",
            (NOW, NOW),
        ),
        (
            "INSERT INTO print_request (requester_id, title, notes, quantity, priority, status,"
            " created_at, updated_at) VALUES (1, 'Hook', '', 1, 'normal', 'submitted', ?, ?)",
            (NOW, NOW),
        ),
        (
            "INSERT INTO printer (id, name, serial, host, access_code)"
            " VALUES (1, 'P1S', '01P00A000000001', '192.168.1.50', 'sealed')",
            (),
        ),
        (
            "INSERT INTO printer_slot (printer_id, ams_index, tray_index, spool_id, updated_at)"
            " VALUES (1, 0, 0, 1, ?)",
            (NOW,),
        ),
        (
            "INSERT INTO machine_token (name, role, token_hash, created_at)"
            " VALUES ('Home Assistant', 'viewer', 'machine-token-hash', ?)",
            (NOW,),
        ),
        (
            "INSERT INTO push_endpoint (device_id, route, endpoint, registered_at, failures)"
            " VALUES ('scanner', 'fcm', 'fcm-token', ?, 0),"
            " ('phone', 'web_push', 'https://push.example', ?, 0)",
            (NOW, NOW),
        ),
    ]
    statements += [
        (
            "INSERT INTO setting (key, value, secret, updated_at) VALUES (?, ?, 0, ?)",
            (key, f"live {key}", NOW),
        )
        for key in SCRUBBED_SETTINGS + KEPT_SETTINGS
    ]
    with sqlite3.connect(path) as db:
        for sql, params in statements:
            db.execute(sql, params)
    db.close()


def _table(path: Path, table: str) -> list[tuple[object, ...]]:
    return _rows(path, f'SELECT * FROM "{table}" ORDER BY 1')  # noqa: S608 - test tables


def _kept_settings(path: Path) -> list[tuple[object, ...]]:
    return [row for row in _table(path, "setting") if row[0] in KEPT_SETTINGS]


def _restore_live(backups: Path, template: Path, settings: Settings, capsys) -> tuple[Path, str]:
    live = _db(backups / "filament-20261120T080000Z.db", template)
    _add_live_data(live)
    assert main(["restore", "--for-test", str(backups)], settings=settings) == 0
    return live, capsys.readouterr().out


def test_removes_what_could_reach_the_household(
    backups: Path, target: Path, settings: Settings, migrated_template: Path, capsys
) -> None:
    _, out = _restore_live(backups, migrated_template, settings, capsys)

    assert {key for (key,) in _rows(target, "SELECT key FROM setting")} == set(KEPT_SETTINGS)
    for table in ("printer", "printer_slot", "machine_token", "push_endpoint"):
        assert _table(target, table) == [], table
    assert "removed 11 settings, 1 printer, 1 machine token, 2 push registrations" in out


def test_deletes_devices_with_no_history_and_revokes_the_rest(
    backups: Path, target: Path, settings: Settings, migrated_template: Path, capsys
) -> None:
    _, out = _restore_live(backups, migrated_template, settings, capsys)

    [(device_id, revoked_at, token_hash)] = _rows(
        target, "SELECT id, revoked_at, token_hash FROM device"
    )
    assert device_id == "scanner"
    assert revoked_at is not None
    assert token_hash not in (SCANNER_TOKEN, PHONE_TOKEN)
    assert "1 device deleted, 1 revoked" in out


def test_keeps_accounts_inventory_requests_and_firebase(
    backups: Path, target: Path, settings: Settings, migrated_template: Path, capsys
) -> None:
    live, _ = _restore_live(backups, migrated_template, settings, capsys)

    for table in KEPT_TABLES:
        assert _table(target, table) == _table(live, table), table
    assert _kept_settings(target) == _kept_settings(live)


# The revision before the newest, and one from before settings, printer slots, machine
# tokens and push registrations existed.
EARLIER = "72db02de11e5"
EARLIEST_WITH_USERS = "4c7498d5acb1"


def _at_revision(path: Path, revision: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    upgrade(f"sqlite:///{path}", revision)
    return path


def _revision(path: Path) -> list[tuple[object, ...]]:
    return _rows(path, "SELECT version_num FROM alembic_version")


def test_an_earlier_schema_is_scrubbed_and_not_migrated(
    backups: Path, target: Path, settings: Settings, tmp_path: Path, capsys
) -> None:
    template = _at_revision(tmp_path / "earlier.db", EARLIER)

    live, out = _restore_live(backups, template, settings, capsys)

    assert _revision(target) == [(EARLIER,)]
    assert {key for (key,) in _rows(target, "SELECT key FROM setting")} == set(KEPT_SETTINGS)
    for table in KEPT_TABLES:
        assert _table(target, table) == _table(live, table), table
    assert "removed 11 settings, 1 printer, 1 machine token, 2 push registrations" in out
    assert "1 device deleted, 1 revoked" in out


def test_tables_an_old_schema_lacks_are_skipped(
    backups: Path, target: Path, settings: Settings, capsys
) -> None:
    live = _at_revision(backups / "filament-20261106T080000Z.db", EARLIEST_WITH_USERS)
    _run(
        live,
        "INSERT INTO device (id, name, token_hash, created_at) VALUES ('scanner', 'S', 'h', ?)",
        NOW,
    )

    code = main(["restore", "--for-test", str(backups)], settings=settings)

    assert code == 0
    assert _revision(target) == [(EARLIEST_WITH_USERS,)]
    assert _table(target, "device") == []
    assert "removed 0 settings, 0 printers, 0 machine tokens, 0 push registrations" in (
        capsys.readouterr().out
    )


def test_refuses_a_database_that_is_not_a_file(
    backups: Path, migrated_template: Path, capsys
) -> None:
    _db(backups / "filament-20261120T080000Z.db", migrated_template)
    in_memory = Settings(database_url="sqlite://", _env_file=None)

    code = main(["restore", "--for-test", str(backups)], settings=in_memory)

    assert code == 1
    assert "DATABASE_URL must be a SQLite file" in capsys.readouterr().err
