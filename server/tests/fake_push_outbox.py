"""A push transport for tests: it records each Web Push instead of sending it, and can be told
to answer 404, 410, a 5xx or to time out. A test phone holds the Web Push keys a real phone
would, so tests can decrypt what was sent to it and check the VAPID signature."""

import base64
import json
import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import http_ece
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid.jwt import decode

from filament_tracker.push.transport import PushError
from filament_tracker.push.webpush import PushMessage


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class TestPhone:
    """A phone's Web Push subscription: its push service URL and its keys."""

    __test__ = False

    def __init__(self, endpoint: str = "https://push.example.com/up/abc123") -> None:
        self.endpoint = endpoint
        # The device it is, once set up.
        self.device_id = ""
        self._key = ec.generate_private_key(ec.SECP256R1())
        self._auth = b"0123456789abcdef"

    def subscription(self) -> dict[str, str]:
        """The body a phone registers with."""
        public = self._key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        return {
            "route": "web_push",
            "endpoint": self.endpoint,
            "p256dh": b64url(public),
            "auth": b64url(self._auth),
        }

    def decrypt(self, message: PushMessage) -> dict[str, Any]:
        """The payload, decrypted with this phone's keys (RFC 8291), which proves it was
        encrypted for this phone."""
        assert message.headers["Content-Encoding"] == "aes128gcm"
        plain = http_ece.decrypt(
            message.body, private_key=self._key, auth_secret=self._auth, version="aes128gcm"
        )
        return json.loads(plain)


def vapid_claims(message: PushMessage, public_key: str) -> dict[str, Any]:
    """The VAPID JWT's claims (RFC 8292), once its signature checks out against the server's
    public key, which the header must also name."""
    scheme, _, params = message.headers["Authorization"].partition(" ")
    assert scheme == "vapid"
    parts = dict(p.split("=", 1) for p in params.split(","))
    assert parts["k"] == public_key
    claims = decode(parts["t"], public_key)
    origin = urlsplit(message.endpoint)
    assert claims["aud"] == f"{origin.scheme}://{origin.netloc}"
    return claims


@dataclass
class _Answer:
    status: int | None  # None: time out


class FakePushOutbox:
    def __init__(self) -> None:
        self.sent: list[PushMessage] = []
        self.attempts = 0
        self._answers: list[_Answer] = []
        self._lock = threading.Lock()
        self.delivered = threading.Event()

    def answer(self, *statuses: int | None) -> None:
        """Answer the next sends with these statuses in turn (None times out); after them,
        201 again."""
        self._answers.extend(_Answer(s) for s in statuses)

    def post(self, message: PushMessage) -> int:
        with self._lock:
            self.attempts += 1
            answer = self._answers.pop(0) if self._answers else _Answer(201)
            if answer.status is None:
                raise PushError("The push service didn't answer in time.")
            if 200 <= answer.status < 300:
                self.sent.append(message)
        self.delivered.set()
        return answer.status
