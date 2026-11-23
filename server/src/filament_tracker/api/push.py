"""A user's phone registering for phone notifications, with the signed-in session.

These answer from outside the LAN too, unlike device-token routes (ADR-0006), so a phone
registers away from home. A device token alone is refused: each route needs the signed-in
session, and accepts only a phone that belongs to the signed-in user and isn't revoked. A
shared phone, another user's phone or a revoked one answers 404, as a phone that doesn't
exist does.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, Response, status

from filament_tracker.api.push_schemas import (
    FirebaseClientOut,
    PushConfigOut,
    PushEndpointIn,
    PushEndpointOut,
    TestPushOut,
    WebPushEndpointIn,
)
from filament_tracker.auth import DbSession, SignedInUser
from filament_tracker.db.models import Device
from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.db.types import utcnow
from filament_tracker.push.firebase import firebase
from filament_tracker.push.messages import Outcome, Push
from filament_tracker.push.payload import phone_payload
from filament_tracker.push.sender import PushSender
from filament_tracker.services.cooldown import Cooldowns

logger = logging.getLogger(__name__)
router = APIRouter(tags=["phone notifications"])

NOT_YOUR_PHONE = "no such phone of yours"
NOT_REGISTERED = "This phone isn't registered for phone notifications."
TOO_SOON = "Wait a few seconds before sending another test notification."
TEST_KIND = "test"
TEST_TITLE = "Test notification"
TEST_TEXT = "Phone notifications work on this phone."
SENT = "Sent a test notification to this phone."


def _own_phone(session: DbSession, caller: SignedInUser, device_id: str) -> Device:
    """The signed-in user's phone `device_id`, if it isn't revoked; 404 otherwise."""
    assert caller.user is not None  # noqa: S101 - guaranteed by SignedInUser
    device = session.get(Device, device_id)
    if device is None or device.user_id != caller.user.id or device.revoked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_YOUR_PHONE)
    return device


@router.get("/push/config", response_model=PushConfigOut)
def push_config(_: SignedInUser, request: Request, response: Response) -> PushConfigOut:
    """What a signed-in user's phone registers for phone notifications with."""
    response.headers["Cache-Control"] = "no-store"
    setup = firebase(request.app.state.settings_store)
    client = None if setup is None else FirebaseClientOut(**asdict(setup.client))
    return PushConfigOut(vapid_public_key=request.app.state.vapid_keys.public, firebase=client)


@router.put("/push/devices/{device_id}", response_model=PushEndpointOut)
def register(
    device_id: str, body: PushEndpointIn, caller: SignedInUser, session: DbSession
) -> PushEndpointOut:
    """Register, or replace, the phone's push endpoint. The app sends it on every start and
    sign-in: the same endpoint again keeps when it was registered and its successes and
    failures, so a phone that stopped getting them is still dropped after 30 days."""
    device = _own_phone(session, caller, device_id)
    web_push = isinstance(body, WebPushEndpointIn)
    given = (
        body.route,
        body.endpoint,
        body.p256dh if web_push else None,
        body.auth if web_push else None,
    )
    endpoint = session.get(PushEndpoint, device.id)
    if endpoint is None or given != (
        endpoint.route,
        endpoint.endpoint,
        endpoint.p256dh,
        endpoint.auth,
    ):
        endpoint = endpoint or PushEndpoint(device_id=device.id)
        endpoint.route, endpoint.endpoint, endpoint.p256dh, endpoint.auth = given
        endpoint.registered_at = utcnow()
        endpoint.last_success_at = None
        endpoint.failures = 0
        endpoint.failing_since = None
        session.add(endpoint)
        session.commit()
        logger.info("phone %s registered for phone notifications", device.id)
    return PushEndpointOut(
        device_id=device.id, route=endpoint.route, registered_at=endpoint.registered_at
    )


@router.delete("/push/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(device_id: str, caller: SignedInUser, session: DbSession) -> Response:
    """Remove the phone's push endpoint, as the app does on Unlink and sign-out."""
    device = _own_phone(session, caller, device_id)
    endpoint = session.get(PushEndpoint, device.id)
    if endpoint is not None:
        session.delete(endpoint)
        session.commit()
        logger.info("phone %s removed its push endpoint", device.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/push/devices/{device_id}/test", response_model=TestPushOut)
def send_test(
    device_id: str, caller: SignedInUser, session: DbSession, request: Request
) -> TestPushOut:
    """Send a test phone notification to the caller's own phone and wait for the result; at
    most one every 30 seconds for each phone."""
    device = _own_phone(session, caller, device_id)
    if session.get(PushEndpoint, device.id) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_REGISTERED)
    cooldowns: Cooldowns = request.app.state.test_push_cooldowns
    if not cooldowns.start(device.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_SOON)
    sender: PushSender = request.app.state.push
    payload = phone_payload(TEST_KIND, TEST_TITLE, TEST_TEXT, "/")
    result = sender.send_now(Push(device.id, payload))
    if result.outcome == Outcome.SENT:
        return TestPushOut(ok=True, message=SENT)
    return TestPushOut(ok=False, message=result.message or NOT_REGISTERED)
