"""The push transport seam: what the sender hands a built Web Push to.

`create_app` takes one (like `mail_transport`); it defaults to posting with httpx, and tests
pass a fake push outbox.
"""

from typing import Protocol

import httpx

from filament_tracker.push.webpush import PushMessage

TIMEOUT_SECONDS = 15.0


class PushError(Exception):
    """The push service couldn't be reached or didn't answer. The message is safe to show
    and log: it never repeats the service's own text."""


class PushTransport(Protocol):
    def post(self, message: PushMessage) -> int:
        """Send one Web Push and return the push service's status code, or raise
        PushError."""
        ...


class HttpPushTransport:
    def post(self, message: PushMessage) -> int:
        try:
            # Redirects aren't followed, so a push goes only to the URL the phone gave.
            response = httpx.post(
                message.endpoint,
                content=message.body,
                headers=message.headers,
                timeout=TIMEOUT_SECONDS,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            raise PushError("The push service didn't answer in time.") from None
        except httpx.HTTPError:
            raise PushError("The push service couldn't be reached.") from None
        return response.status_code
