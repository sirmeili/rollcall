"""An FCM message (Firebase Cloud Messaging, HTTP v1 API) for one phone of the google flavor,
sent with an OAuth access token from the service-account key.

The payload is the Web Push one, as FCM data, which the app shows itself. The access token is
asked for with an assertion signed by the key (RFC 7523) and kept until 5 minutes before it
expires; a different key, or FCM refusing it, asks again.
"""

import base64
import json
import threading
import time
from collections.abc import Callable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from filament_tracker.push.fcm_account import ServiceAccountKey
from filament_tracker.push.transport import TOKEN_URL, PushTransport
from filament_tracker.push.webpush import TTL_SECONDS, PushMessage

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
ASSERTION_SECONDS = 3600
# An access token is asked for again this long before it expires.
EARLY_SECONDS = 300
# Every notification is shown, which is what Google asks high priority to be kept for.
PRIORITY = "high"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _part(value: dict[str, object]) -> str:
    return _b64url(json.dumps(value, separators=(",", ":")).encode())


def assertion(account: ServiceAccountKey, now: float) -> str:
    """The signed JWT asking Google for an access token to send FCM messages."""
    issued = int(now)
    claims = {
        "iss": account.email,
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": issued,
        "exp": issued + ASSERTION_SECONDS,
    }
    signing_input = f"{_part({'alg': 'RS256', 'typ': 'JWT'})}.{_part(claims)}"
    signature = account.private_key.sign(
        signing_input.encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    return f"{signing_input}.{_b64url(signature)}"


class AccessTokens:
    """FCM's OAuth access token for the key in use, kept until it nearly expires."""

    def __init__(self, transport: PushTransport, clock: Callable[[], float] = time.time) -> None:
        self._transport = transport
        self._clock = clock
        self._lock = threading.Lock()
        self._for: tuple[str, int] | None = None
        self._token = ""
        self._until = 0.0

    def get(self, account: ServiceAccountKey) -> str:
        """An access token for `account`, or PushError."""
        with self._lock:
            now = self._clock()
            which = (account.email, account.private_key.public_key().public_numbers().n)
            if self._for != which or now >= self._until:
                answer = self._transport.access_token(assertion(account, now))
                self._for = which
                self._token = answer.token
                self._until = now + answer.expires_in - EARLY_SECONDS
            return self._token

    def forget(self) -> None:
        """Forget the token FCM refused, so the next send asks for a new one."""
        with self._lock:
            self._for = None
            self._token = ""
            self._until = 0.0


def fcm_message(project_id: str, token: str, payload: bytes, access_token: str) -> PushMessage:
    """The message carrying `payload` (a JSON object of strings) to the phone with FCM
    registration token `token`."""
    body = {
        "message": {
            "token": token,
            "data": json.loads(payload),
            "android": {"priority": PRIORITY, "ttl": f"{TTL_SECONDS}s"},
        }
    }
    return PushMessage(
        endpoint=f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        body=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(),
    )
