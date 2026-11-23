"""Request and response bodies for sign-in, the current user and user management."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from filament_tracker.api.schemas import Strict
from filament_tracker.domain.enums import Channel, NotificationKind, Role
from filament_tracker.services.accounts import MAX_PASSWORD

# Length limits here only stop absurd input; the password rules are checked by the service
# so they give one clear message.
Username = Annotated[str, StringConstraints(min_length=1, max_length=64)]
Password = Annotated[str, StringConstraints(min_length=1, max_length=MAX_PASSWORD)]
# Checked by mail/address.py; this limit only stops absurd input. Empty clears it.
EmailText = Annotated[str, StringConstraints(max_length=1024)]


class LoginRequest(Strict):
    username: Username
    password: Password


class PasswordChange(Strict):
    current_password: Password
    new_password: Password


class NotificationSetting(BaseModel):
    kind: NotificationKind
    channel: Channel
    on: bool
    # True while the user hasn't chosen: `on` is the default.
    default: bool


class NotificationChoiceIn(Strict):
    kind: NotificationKind
    channel: Channel
    on: bool


class UserBase(BaseModel):
    id: int
    username: str
    role: Role
    # May submit print requests, alongside the role (ADR-0017).
    requester: bool
    # Optional and never verified.
    email: str | None


class Me(UserBase):
    # The server's time zone, in which the web app shows every time.
    time_zone: str
    # Has made a print request, so keeps the Requests page even when no longer a Requester.
    has_requests: bool
    # Notification settings for each kind the user may choose, in the order to list them.
    notifications: list[NotificationSetting]
    # Whether this server can send email at all (an SMTP host is saved).
    email_set_up: bool


class UserOut(UserBase):
    disabled: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(Strict):
    username: Username
    password: Password
    role: Role
    requester: bool = False


class UserUpdate(Strict):
    role: Role | None = None
    requester: bool | None = None
    disabled: bool | None = None
    password: Password | None = None
    # An empty value (or null) clears it; left out, it stays as it is.
    email: EmailText | None = None


class AccountUpdate(Strict):
    """What a user changes on their own Account page. Each field left out stays as it is."""

    # An empty value (or null) clears it.
    email: EmailText | None = None
    # The user's own notification choices; kinds not given keep what they have.
    notifications: list[NotificationChoiceIn] = Field(default_factory=list, max_length=64)
