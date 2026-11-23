"""A push transport for tests: it records each Web Push and FCM message instead of sending it,
and can be told to answer 404, 410, a 5xx or to time out. A test phone holds the Web Push keys
a real phone would, so tests can decrypt what was sent to it and check the VAPID signature. It
also stands in for Google's OAuth token endpoint, recording each signed assertion, so tests
can check it against a made-up service-account key."""

import base64
import json
import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import http_ece
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from py_vapid.jwt import decode

from filament_tracker.push.transport import AccessToken, PushError
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


# Made-up Firebase client settings, in Firebase's formats.
FIREBASE = {
    "firebase_project_id": "rollcall-test",
    "firebase_app_id": "1:123456789012:android:0123456789abcdef",
    "firebase_api_key": "AIza" + "Sy0123456789abcdefghijklmnopqrstu",
    "firebase_sender_id": "123456789012",
}


@dataclass(frozen=True)
class ServiceAccount:
    """A made-up Firebase service-account key: its JSON, as Firebase's console downloads it,
    and its RSA key, to check what it signed."""

    json: str
    email: str
    key: rsa.RSAPrivateKey


def service_account(project_id: str = "rollcall-test") -> ServiceAccount:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    email = f"firebase-adminsdk-abc12@{project_id}.iam.gserviceaccount.com"
    body = {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": "0123456789abcdef0123456789abcdef01234567",
        "private_key": pem,
        "client_email": email,
        "client_id": "123456789012345678901",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return ServiceAccount(json.dumps(body, indent=2), email, key)


class FcmPhone:
    """A phone of the google flavor: its FCM registration token."""

    __test__ = False

    def __init__(self, token: str = "fcm-token_abc:123-XYZ") -> None:  # noqa: S107 - test value
        self.token = token
        self.device_id = ""

    def subscription(self) -> dict[str, str]:
        """The body a phone registers with."""
        return {"route": "fcm", "endpoint": self.token}

    def data(self, messages: list[PushMessage]) -> list[dict[str, Any]]:
        """The data of each FCM message sent to this phone."""
        bodies = [json.loads(m.body)["message"] for m in messages if m.endpoint.startswith(FCM)]
        return [b["data"] for b in bodies if b["token"] == self.token]


FCM = "https://fcm.googleapis.com/v1/projects/"


def assertion_claims(assertion: str, account: ServiceAccount) -> dict[str, Any]:
    """The claims of an OAuth assertion (RFC 7523), once its RS256 signature checks out
    against the service account's public key."""
    header, claims, signature = assertion.split(".")
    account.key.public_key().verify(
        unb64url(signature),
        f"{header}.{claims}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    assert json.loads(unb64url(header)) == {"alg": "RS256", "typ": "JWT"}
    return json.loads(unb64url(claims))


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
        # The OAuth assertions FCM access tokens were asked for with.
        self.assertions: list[str] = []
        self._token_error = ""

    def answer(self, *statuses: int | None) -> None:
        """Answer the next sends with these statuses in turn (None times out); after them,
        201 again."""
        self._answers.extend(_Answer(s) for s in statuses)

    def refuse_tokens(
        self, error: str = "Google refused the Firebase service-account key."
    ) -> None:
        """Answer the next requests for an OAuth access token with this error."""
        self._token_error = error

    def access_token(self, assertion: str) -> AccessToken:
        """Google's OAuth token endpoint: records the signed assertion and answers with a new
        access token, good for an hour."""
        with self._lock:
            if self._token_error:
                raise PushError(self._token_error)
            self.assertions.append(assertion)
            return AccessToken(f"fake-access-token-{len(self.assertions)}", 3600)

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
