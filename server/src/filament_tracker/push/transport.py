"""The push transport seam: what the sender hands a built Web Push or FCM message to, and
where it gets FCM's OAuth access tokens.

`create_app` takes one (like `mail_transport`); it defaults to posting with httpx, and tests
pass a fake push outbox.
"""

from dataclasses import dataclass, field
from typing import Protocol

import httpx

from filament_tracker.push.webpush import PushMessage

TIMEOUT_SECONDS = 15.0
# Google's OAuth token endpoint. Fixed here, never read from the service-account key, so the
# signed assertion goes only to Google.
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a URL, not a secret
JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
REFUSED = "Google refused the Firebase service-account key."
UNREACHABLE = "Google's sign-in for Firebase couldn't be reached."


@dataclass(frozen=True)
class AccessToken:
    # Never shown in a repr, so never in a log or a traceback.
    token: str = field(repr=False)
    # Seconds it is good for, from when it was given.
    expires_in: int


class PushError(Exception):
    """The push service couldn't be reached or didn't answer. The message is safe to show
    and log: it never repeats the service's own text."""


class PushTransport(Protocol):
    def post(self, message: PushMessage) -> int:
        """Send one Web Push or FCM message and return the push service's status code, or
        raise PushError."""
        ...

    def access_token(self, assertion: str) -> AccessToken:
        """Exchange a signed OAuth assertion (RFC 7523) at Google for an access token, or
        raise PushError."""
        ...


class HttpPushTransport:
    """Posts with httpx; `transport` replaces the network in tests."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def post(self, message: PushMessage) -> int:
        try:
            # Redirects aren't followed, so a push goes only to the URL the phone gave.
            with httpx.Client(
                transport=self._transport, timeout=TIMEOUT_SECONDS, follow_redirects=False
            ) as client:
                response = client.post(
                    message.endpoint, content=message.body, headers=message.headers
                )
        except httpx.TimeoutException:
            raise PushError("The push service didn't answer in time.") from None
        except httpx.HTTPError:
            raise PushError("The push service couldn't be reached.") from None
        return response.status_code

    def access_token(self, assertion: str) -> AccessToken:
        form = {"grant_type": JWT_BEARER, "assertion": assertion}
        try:
            with httpx.Client(
                transport=self._transport, timeout=TIMEOUT_SECONDS, follow_redirects=False
            ) as client:
                response = client.post(TOKEN_URL, data=form)
        except httpx.HTTPError:
            raise PushError(UNREACHABLE) from None
        if response.status_code in (400, 401, 403):
            raise PushError(REFUSED)
        try:
            body = response.json()
            token = AccessToken(str(body["access_token"]), int(body["expires_in"]))
        except (ValueError, KeyError, TypeError):
            raise PushError(UNREACHABLE) from None
        if response.status_code != 200 or not token.token:
            raise PushError(UNREACHABLE)
        return token
