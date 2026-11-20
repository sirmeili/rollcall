"""The settings that can be saved in the app, by group.

Each one names its `.env` setting (the starting value), whether it is a secret, and how a
value is checked. Check errors never repeat the value, which may be a secret or hold one.
Printers are not here: they have their own table and page.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parseaddr
from functools import cache
from urllib.parse import urlsplit
from zoneinfo import available_timezones

from filament_tracker.ha.broker import parse_mqtt_url
from filament_tracker.ha.rest import parse_ha_url
from filament_tracker.mail.address import clean_address
from filament_tracker.mail.transport import SECURITIES

MAX_VALUE = 1024
PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}(/[A-Za-z0-9_-]{1,64}){0,3}$")
SALT_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}){1,64}")
ACCESS_ID_PATTERN = re.compile(r"[A-Za-z0-9]{16,64}\.access")
# Cloudflare Access service token secrets: "cfast_" with 40 characters and an 8-character
# checksum since 2026-08-26, or the older form of letters and digits, which still works.
ACCESS_SECRET_PATTERN = re.compile(r"cfast_[A-Za-z0-9]{48}|[A-Za-z0-9]{32,128}")
MIN_SESSION_DAYS, MAX_SESSION_DAYS = 1, 365
CATALOG_SYNCS = ("off", "daily", "weekly")
MIN_CUTOFF, MAX_CUTOFF = 0.5, 50.0
HOST_PATTERN = re.compile(r"[A-Za-z0-9.-]{1,253}|\[[0-9A-Fa-f:.]{2,45}\]")


def _mqtt_url(value: str) -> str:
    parse_mqtt_url(value)
    return value


def _ha_url(value: str) -> str:
    return parse_ha_url(value)


def _prefix(value: str) -> str:
    if not PREFIX_PATTERN.fullmatch(value):
        raise ValueError("use letters, digits, - and _, with up to three / between parts")
    return value


@cache
def time_zones() -> frozenset[str]:
    """IANA time zone names (from tzdata, so the same on every platform)."""
    return frozenset(available_timezones())


def time_zone(value: str) -> str:
    """An IANA time zone name such as America/New_York. The error never repeats it."""
    if value not in time_zones():
        raise ValueError("use a time zone name such as America/New_York or UTC")
    return value


def session_days(value: str) -> str:
    try:
        days = int(value)
    except ValueError:
        raise ValueError("use a whole number of days") from None
    if not MIN_SESSION_DAYS <= days <= MAX_SESSION_DAYS:
        raise ValueError(f"use {MIN_SESSION_DAYS} to {MAX_SESSION_DAYS} days")
    return str(days)


def catalog_sync(value: str) -> str:
    if value not in CATALOG_SYNCS:
        raise ValueError("use off, daily or weekly")
    return value


def similarity_cutoff(value: str) -> str:
    """A ΔE from 0.5 to 50, written without trailing zeros ("10", "2.5")."""
    problem = f"use a number from {MIN_CUTOFF:g} to {MAX_CUTOFF:g}"
    try:
        cutoff = float(value)
    except ValueError:
        raise ValueError(problem) from None
    if not MIN_CUTOFF <= cutoff <= MAX_CUTOFF:
        raise ValueError(problem)
    return f"{cutoff:g}"


STORE_ADDRESS_PROBLEM = "Enter an https address with no path, like https://us.store.bambulab.com"


def store_address(value: str) -> str:
    """An https address with a host and no path, query, fragment or user info. One trailing
    slash is dropped."""
    value = value.removesuffix("/")
    try:
        parts = urlsplit(value)
        port = parts.port  # a malformed port raises
    except ValueError:
        raise ValueError(STORE_ADDRESS_PROBLEM) from None
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.path
        or parts.query
        or parts.fragment
        or "@" in parts.netloc
        or "?" in value
        or "#" in value
        or (port is not None and not 0 < port < 65536)
    ):
        raise ValueError(STORE_ADDRESS_PROBLEM)
    return value


PUBLIC_URL_PROBLEM = "Enter an https address with no path, like https://rollcall.example.com"


def public_url(value: str) -> str:
    """The address the family opens RollCall at, checked like the store address."""
    try:
        return store_address(value)
    except ValueError:
        raise ValueError(PUBLIC_URL_PROBLEM) from None


def smtp_host(value: str) -> str:
    """A host name or an IP address, with no port or scheme."""
    if not HOST_PATTERN.fullmatch(value):
        raise ValueError("use the mail server's host name, like smtp.example.com")
    return value


def smtp_port(value: str) -> str:
    problem = "use a port from 1 to 65535"
    try:
        port = int(value)
    except ValueError:
        raise ValueError(problem) from None
    if not 0 < port < 65536:
        raise ValueError(problem)
    return str(port)


def smtp_security(value: str) -> str:
    if value not in SECURITIES:
        *first, last = SECURITIES
        raise ValueError(f"use {', '.join(first)} or {last}")
    return value


def smtp_from(value: str) -> str:
    """An address, optionally with a name: rollcall@example.com or
    RollCall <rollcall@example.com>. The error never repeats it."""
    problem = "use an address like rollcall@example.com or RollCall <rollcall@example.com>"
    name, address = parseaddr(value, strict=True)
    try:
        if not address or clean_address(address) is None:
            raise ValueError(problem)
    except ValueError:
        raise ValueError(problem) from None
    return value


def kdf_salt(value: str) -> str:
    """The key-derivation constant as upper-case hex. The error never repeats it."""
    if not SALT_PATTERN.fullmatch(value):
        raise ValueError("use hex: an even number of digits, at most 128")
    return value.upper()


def access_client_id(value: str) -> str:
    """A Cloudflare Access service token's Client ID. The error never repeats it."""
    if not ACCESS_ID_PATTERN.fullmatch(value):
        raise ValueError("use the service token's Client ID from Cloudflare, ending in .access")
    return value


def access_client_secret(value: str) -> str:
    """A Cloudflare Access service token's Client Secret. The error never repeats it."""
    if not ACCESS_SECRET_PATTERN.fullmatch(value):
        raise ValueError("use the service token's Client Secret from Cloudflare")
    return value


def _plain(value: str) -> str:
    return value


@dataclass(frozen=True)
class SettingDef:
    key: str
    group: str
    # The attribute of config.Settings that holds the .env value.
    env: str
    secret: bool = False
    # Whether the setting may be empty (meaning off or none).
    optional: bool = True
    check: Callable[[str], str] = _plain

    def clean(self, value: str) -> str:
        """The value to store: trimmed and checked. Raises ValueError, never echoing it."""
        value = value.strip()
        if len(value) > MAX_VALUE:
            raise ValueError(f"at most {MAX_VALUE} characters")
        if not value:
            if not self.optional:
                raise ValueError("needs a value")
            return ""
        return self.check(value)


GENERAL = "general"
HOME_ASSISTANT = "home-assistant"
SCANNERS = "scanners"
CATALOG = "catalog"
EMAIL = "email"

DEFINITIONS: tuple[SettingDef, ...] = (
    SettingDef("tz", GENERAL, "tz", optional=False, check=time_zone),
    SettingDef("session_days", GENERAL, "session_days", optional=False, check=session_days),
    SettingDef("mqtt_url", HOME_ASSISTANT, "mqtt_url", check=_mqtt_url),
    SettingDef("mqtt_user", HOME_ASSISTANT, "mqtt_user"),
    SettingDef("mqtt_password", HOME_ASSISTANT, "mqtt_password", secret=True),
    SettingDef(
        "ha_discovery_prefix", HOME_ASSISTANT, "ha_discovery_prefix", optional=False, check=_prefix
    ),
    SettingDef("ha_url", HOME_ASSISTANT, "ha_url", check=_ha_url),
    SettingDef("ha_token", HOME_ASSISTANT, "ha_token", secret=True),
    SettingDef("bambu_kdf_salt", SCANNERS, "bambu_kdf_salt", secret=True, check=kdf_salt),
    SettingDef("cf_access_client_id", SCANNERS, "cf_access_client_id", check=access_client_id),
    SettingDef(
        "cf_access_client_secret",
        SCANNERS,
        "cf_access_client_secret",
        secret=True,
        check=access_client_secret,
    ),
    SettingDef("catalog_sync", CATALOG, "catalog_sync", optional=False, check=catalog_sync),
    SettingDef(
        "similarity_cutoff", CATALOG, "similarity_cutoff", optional=False, check=similarity_cutoff
    ),
    SettingDef("store_address", CATALOG, "store_address", optional=False, check=store_address),
    SettingDef("smtp_host", EMAIL, "smtp_host", check=smtp_host),
    SettingDef("smtp_port", EMAIL, "smtp_port", optional=False, check=smtp_port),
    SettingDef("smtp_security", EMAIL, "smtp_security", optional=False, check=smtp_security),
    SettingDef("smtp_user", EMAIL, "smtp_user"),
    SettingDef("smtp_password", EMAIL, "smtp_password", secret=True),
    SettingDef("smtp_from", EMAIL, "smtp_from", check=smtp_from),
    SettingDef("public_url", EMAIL, "public_url", check=public_url),
)

BY_KEY = {d.key: d for d in DEFINITIONS}
GROUPS = frozenset(d.group for d in DEFINITIONS)


def group(name: str) -> tuple[SettingDef, ...]:
    return tuple(d for d in DEFINITIONS if d.group == name)
