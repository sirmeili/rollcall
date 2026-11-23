"""What the phone sender sends, and what each answer means: a push names a phone, and its
message is built by the route the phone registered, a Web Push or an FCM message when
Firebase is set up. The phone's endpoint is read when the message is built, so a phone
removed, revoked or disabled in the meantime gets nothing.

What each answer means:

- 2xx: sent.
- 404 or 410: the phone's endpoint is gone (the app uninstalled, or its data cleared). FCM
  answers 404 for a token that is no longer registered.
- A 5xx or a 429, or no answer: worth trying again.
- From FCM, a 401: the access token was refused, so it is forgotten and asked for again on
  the next try.
- Any other answer (another 4xx): trying again won't help.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.domain.enums import PushRoute
from filament_tracker.push.fcm import AccessTokens, fcm_message
from filament_tracker.push.firebase import Firebase
from filament_tracker.push.keys import VapidKeys
from filament_tracker.push.transport import PushTransport
from filament_tracker.push.webpush import PushMessage, Subscription, web_push

GONE = {404, 410}
TOO_MANY = 429
UNAUTHORIZED = 401
NO_FIREBASE = "Firebase isn't set up on this server."
ACCESS_REFUSED = "Firebase refused the access token; a new one is asked for."


@dataclass(frozen=True)
class Push:
    """One phone notification to deliver to one phone: the payload its push carries."""

    device_id: str
    payload: bytes


class Outcome(StrEnum):
    SENT = "sent"
    # The endpoint is gone, and was dropped.
    GONE = "gone"
    # Worth trying again.
    FAILED = "failed"
    # Failed in a way trying again won't fix.
    REFUSED = "refused"
    # The phone has no endpoint, or may no longer get phone notifications.
    NOWHERE = "nowhere"


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    # Safe to show: never the push service's own text.
    message: str = ""


@dataclass(frozen=True)
class Built:
    """A push's message, and the route it goes by."""

    route: PushRoute
    message: PushMessage


def reachable(endpoint: PushEndpoint) -> bool:
    """Whether the endpoint's phone may get phone notifications: a user's phone, not
    revoked, whose user isn't disabled. A shared phone never does."""
    device = endpoint.device
    return device.revoked_at is None and device.user is not None and device.user.disabled_at is None


class Messages:
    """Builds each push's message by its phone's route, and says what an answer means."""

    def __init__(
        self,
        transport: PushTransport,
        sessions: sessionmaker[Session],
        keys: VapidKeys,
        firebase: Callable[[], Firebase | None],
    ) -> None:
        self._sessions = sessions
        self._keys = keys
        self._firebase = firebase
        self._access_tokens = AccessTokens(transport)

    def build(self, push: Push) -> Built | Result:
        """The message to send by the phone's route, or why there is none. Raises PushError
        when FCM's access token can't be had."""
        with self._sessions() as session:
            endpoint = session.get(PushEndpoint, push.device_id)
            if endpoint is None or not reachable(endpoint):
                return Result(Outcome.NOWHERE)
            route, address = endpoint.route, endpoint.endpoint
            to = Subscription(address, endpoint.p256dh or "", endpoint.auth or "")
        if route == PushRoute.WEB_PUSH:
            return Built(route, web_push(to, push.payload, self._keys))
        firebase = self._firebase()
        if firebase is None:
            return Result(Outcome.NOWHERE, NO_FIREBASE)
        access_token = self._access_tokens.get(firebase.account)
        project = firebase.client.project_id
        return Built(route, fcm_message(project, address, push.payload, access_token))

    def answered(self, route: PushRoute, status: int) -> Result:
        """What the push service's answer means."""
        if 200 <= status < 300:
            return Result(Outcome.SENT)
        if status in GONE:
            return Result(Outcome.GONE, "This phone's push endpoint is gone.")
        if route == PushRoute.FCM and status == UNAUTHORIZED:
            self._access_tokens.forget()
            return Result(Outcome.FAILED, ACCESS_REFUSED)
        said = f"The push service answered {status}."
        if status >= 500 or status == TOO_MANY:
            return Result(Outcome.FAILED, said)
        return Result(Outcome.REFUSED, said)
