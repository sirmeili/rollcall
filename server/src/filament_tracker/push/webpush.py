"""A Web Push message (RFC 8030): the payload encrypted for one phone (RFC 8291, aes128gcm)
and signed with the server's VAPID key (RFC 8292), with a time to live and an urgency."""

import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import http_ece
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02

from filament_tracker.push.keys import VapidKeys, unb64url

# How long a push service keeps a notification for a phone that is off: a week.
TTL_SECONDS = 7 * 24 * 3600
URGENCY = "normal"
# How long the VAPID signature is good for (RFC 8292 allows up to 24 hours).
SIGNATURE_SECONDS = 12 * 3600
# The VAPID contact the push service sees. It names no server or person: PUBLIC_URL may be
# unset, and isn't the push service's business.
SUBJECT = "mailto:rollcall@localhost"


@dataclass(frozen=True)
class PushMessage:
    endpoint: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Subscription:
    """Where and how to reach one phone: its push service URL and its Web Push keys."""

    endpoint: str
    p256dh: str
    auth: str


def origin(url: str) -> str:
    """The scheme, host and port of a push service URL: the VAPID audience."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def web_push(
    to: Subscription, payload: bytes, keys: VapidKeys, *, now: float | None = None
) -> PushMessage:
    """The message carrying `payload` to one phone."""
    body = http_ece.encrypt(
        payload,
        private_key=ec.generate_private_key(ec.SECP256R1()),
        dh=unb64url(to.p256dh),
        auth_secret=unb64url(to.auth),
        version="aes128gcm",
    )
    expires = int(now if now is not None else time.time()) + SIGNATURE_SECONDS
    vapid = Vapid02(keys.private)
    signed = vapid.sign({"aud": origin(to.endpoint), "exp": expires, "sub": SUBJECT})
    return PushMessage(
        endpoint=to.endpoint,
        headers={
            "Authorization": signed["Authorization"],
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(TTL_SECONDS),
            "Urgency": URGENCY,
        },
        body=body,
    )
