"""Scrub a test server's copy of the live data, so it can't reach the household: no email,
Home Assistant or printers, and no device, machine token or push registration that works.

It uses plain SQL on tables and columns every release has had, and skips a table an older
release doesn't have yet, so a database at any schema keeps that schema.
"""

import secrets
from dataclasses import dataclass

from sqlalchemy import Connection, bindparam, inspect, text

from filament_tracker.db.engine import create_db_engine
from filament_tracker.db.types import UtcDateTime, utcnow

# The settings for email (SMTP) and the Home Assistant MQTT broker and REST events. The
# Firebase settings stay, so notifications work on a test phone.
SETTINGS = (
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


@dataclass(frozen=True)
class Scrubbed:
    settings: int
    printers: int
    machine_tokens: int
    push_registrations: int
    devices_deleted: int
    devices_revoked: int

    def __str__(self) -> str:
        return (
            f"{_count(self.settings, 'setting')}, {_count(self.printers, 'printer')},"
            f" {_count(self.machine_tokens, 'machine token')},"
            f" {_count(self.push_registrations, 'push registration')};"
            f" {_count(self.devices_deleted, 'device')} deleted,"
            f" {self.devices_revoked} revoked"
        )


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def scrub(database_url: str) -> Scrubbed:
    engine = create_db_engine(database_url)
    try:
        with engine.begin() as db:
            tables = set(inspect(db).get_table_names())
            push = _delete(db, tables, "push_endpoint")
            _delete(db, tables, "printer_slot")
            printers = _delete(db, tables, "printer")
            tokens = _delete(db, tables, "machine_token")
            settings = _delete_settings(db, tables)
            deleted, revoked = _devices(db, tables)
    finally:
        engine.dispose()
    return Scrubbed(settings, printers, tokens, push, deleted, revoked)


def _delete(db: Connection, tables: set[str], table: str) -> int:
    if table not in tables:
        return 0
    return db.execute(text(f'DELETE FROM "{table}"')).rowcount  # noqa: S608 - our names


def _delete_settings(db: Connection, tables: set[str]) -> int:
    if "setting" not in tables:
        return 0
    statement = text("DELETE FROM setting WHERE key IN :keys").bindparams(
        bindparam("keys", expanding=True)
    )
    return db.execute(statement, {"keys": list(SETTINGS)}).rowcount


def _devices(db: Connection, tables: set[str]) -> tuple[int, int]:
    """Delete the devices no event names. The rest keep their history, so they are revoked,
    with a token hash no token has."""
    if "device" not in tables:
        return 0, 0
    named = "SELECT device_id FROM event WHERE device_id IS NOT NULL"
    deleted = db.execute(text(f"DELETE FROM device WHERE id NOT IN ({named})")).rowcount  # noqa: S608
    revoked = 0
    for (device_id,) in db.execute(text("SELECT id FROM device")).all():
        db.execute(
            text(
                "UPDATE device SET token_hash = :hash, revoked_at = COALESCE(revoked_at, :now)"
                " WHERE id = :id"
            ).bindparams(bindparam("now", type_=UtcDateTime())),
            {"hash": secrets.token_hex(32), "now": utcnow(), "id": device_id},
        )
        revoked += 1
    return deleted, revoked
