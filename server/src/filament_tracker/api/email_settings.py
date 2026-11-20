"""The Email group's Send test email and the sender's last success and failure (Admin only).

The group's settings themselves are read and saved like every other group (api/settings.py).
"""

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from filament_tracker.app_settings.registry import EMAIL
from filament_tracker.auth import Admin, forbidden
from filament_tracker.mail.checks import test_email
from filament_tracker.mail.sender import MailSender
from filament_tracker.mail.transport import MailError

router = APIRouter(tags=["settings"])

NO_ADDRESS = "Add your email address on Account first."


class FailureOut(BaseModel):
    at: datetime
    message: str


class EmailStatusOut(BaseModel):
    # Whether email is set up: an SMTP host is saved.
    on: bool
    last_success: datetime | None
    # Never holds the password or the mail server's own text.
    last_failure: FailureOut | None


class TestEmailOut(BaseModel):
    ok: bool
    message: str


def _sender(request: Request) -> MailSender:
    return request.app.state.mail


@router.get(f"/settings/{EMAIL}/status", response_model=EmailStatusOut)
def email_status(_: Admin, request: Request) -> EmailStatusOut:
    sender = _sender(request)
    failure = sender.last_failure
    return EmailStatusOut(
        on=sender.on,
        last_success=sender.last_success,
        last_failure=FailureOut(at=failure.at, message=failure.message) if failure else None,
    )


@router.post(f"/settings/{EMAIL}/test", response_model=TestEmailOut)
def send_test_email(principal: Admin, request: Request) -> TestEmailOut:
    """Send a test email to the signed-in Admin's address with the saved settings, and wait
    for the result."""
    user = principal.user
    if user is None:
        raise forbidden("only a signed-in Admin can send a test email")
    if not user.email:
        return TestEmailOut(ok=False, message=NO_ADDRESS)
    try:
        _sender(request).send_now(test_email(user.email))
    except MailError as error:
        return TestEmailOut(ok=False, message=str(error))
    return TestEmailOut(ok=True, message=f"Sent a test email to {user.email}.")
