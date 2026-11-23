"""Request and response bodies for a user's phone registering for phone notifications."""

import binascii
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from filament_tracker.api.schemas import Strict
from filament_tracker.domain.enums import PushRoute
from filament_tracker.push.keys import unb64url

# P-256 public keys are 65 bytes uncompressed; auth secrets 16 (RFC 8291).
P256_POINT_BYTES = 65
AUTH_BYTES = 16


def _https(url: str) -> str:
    if not url.startswith("https://") or len(url) <= len("https://"):
        raise ValueError("must be an https:// URL")
    return url


def _bytes(length: int, first: int | None = None) -> Callable[[str], str]:
    """A check that the text is base64url of `length` bytes, starting with `first`."""

    def check(text: str) -> str:
        try:
            raw = unb64url(text)
        except (binascii.Error, ValueError):
            raise ValueError("must be base64url") from None
        if len(raw) != length or (first is not None and raw[0] != first):
            raise ValueError(f"must be {length} bytes")
        return text

    return check


Endpoint = Annotated[str, StringConstraints(max_length=2048), AfterValidator(_https)]
P256dh = Annotated[
    str, StringConstraints(max_length=128), AfterValidator(_bytes(P256_POINT_BYTES, 4))
]
Auth = Annotated[str, StringConstraints(max_length=64), AfterValidator(_bytes(AUTH_BYTES))]
# FCM registration tokens: letters, digits, -, _ and :, about 150 to 200 long.
FcmToken = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_:-]{1,4096}$")]


class FirebaseClientOut(BaseModel):
    """What a phone of the google flavor starts Firebase with."""

    project_id: str
    app_id: str
    api_key: str
    sender_id: str


class PushConfigOut(BaseModel):
    # What the phone registers with its push distributor (the applicationServerKey).
    vapid_public_key: str
    # Firebase's client settings when the server sends through FCM; None otherwise.
    firebase: FirebaseClientOut | None


class WebPushEndpointIn(Strict):
    route: Literal[PushRoute.WEB_PUSH]
    # The push service's URL for this phone.
    endpoint: Endpoint
    # The phone's Web Push keys, base64url.
    p256dh: P256dh
    auth: Auth


class FcmEndpointIn(Strict):
    route: Literal[PushRoute.FCM]
    # The phone's FCM registration token.
    endpoint: FcmToken


PushEndpointIn = Annotated[WebPushEndpointIn | FcmEndpointIn, Field(discriminator="route")]


class PushEndpointOut(BaseModel):
    device_id: str
    route: PushRoute
    registered_at: datetime


class TestPushOut(BaseModel):
    ok: bool
    message: str
