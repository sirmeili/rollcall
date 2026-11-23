"""Sign in, sign out, the current user, and changing one's own email address, notification
settings and password."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from filament_tracker.api.account_schemas import (
    AccountUpdate,
    LoginRequest,
    Me,
    NotificationSetting,
    PasswordChange,
)
from filament_tracker.api.deps import mail_sender
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.auth import (
    SESSION_COOKIE,
    DbSession,
    SignedInUser,
    check_csrf,
    current_session,
    forbidden,
    set_session_cookie,
    settings_of,
    unauthorized,
)
from filament_tracker.db.models import User
from filament_tracker.db.types import utcnow
from filament_tracker.net import client_ip
from filament_tracker.notifications.phone import has_phone
from filament_tracker.notifications.settings import (
    Choice,
    NotChoosable,
    choose,
    notification_settings,
)
from filament_tracker.print_requests.access import has_requests
from filament_tracker.services.accounts import (
    AccountError,
    authenticate,
    email_address,
    set_password,
    start_session,
)
from filament_tracker.services.throttle import LoginThrottle

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_FAILED = "invalid username or password"
TOO_MANY = "too many failed attempts; try again later"


def _throttle(request: Request) -> LoginThrottle:
    return request.app.state.login_throttle


def _address(request: Request) -> str:
    return str(client_ip(request, settings_of(request)) or "unknown")


def _store(request: Request) -> SettingsStore:
    return request.app.state.settings_store


def me_out(request: Request, session: Session, user: User) -> Me:
    owns_requests = has_requests(session, user)
    return Me(
        id=user.id,
        username=user.username,
        role=user.role,
        requester=user.requester,
        email=user.email,
        has_requests=owns_requests,
        notifications=[
            NotificationSetting(kind=s.kind, channel=s.channel, on=s.on, default=s.default)
            for s in notification_settings(session, user, has_requests=owns_requests)
        ],
        email_set_up=mail_sender(request).on,
        phone_registered=has_phone(session, user),
        time_zone=_store(request).time_zone(),
    )


@router.post("/login", response_model=Me)
def login(body: LoginRequest, request: Request, response: Response, session: DbSession) -> Me:
    check_csrf(request)
    throttle, address = _throttle(request), _address(request)
    if throttle.blocked(body.username, address):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
    user = authenticate(session, body.username, body.password)
    if user is None:
        throttle.failed(body.username, address)
        raise unauthorized(LOGIN_FAILED)
    throttle.succeeded(body.username)
    days = _store(request).session_days()
    token = start_session(session, user, days, utcnow())
    session.commit()
    set_session_cookie(request, response, token, days)
    return me_out(request, session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, session: DbSession) -> Response:
    """End this browser's session. Succeeds even if it had already ended."""
    check_csrf(request)
    user_session = current_session(request, session)
    if user_session is not None:
        session.delete(user_session)
        session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings_of(request).cookie_secure,
        samesite="strict",
    )
    return response


@router.get("/me", response_model=Me)
def me(caller: SignedInUser, request: Request, session: DbSession) -> Me:
    assert caller.user is not None  # noqa: S101 - guaranteed by SignedInUser
    return me_out(request, session, caller.user)


@router.patch("/me", response_model=Me)
def update_account(
    body: AccountUpdate, caller: SignedInUser, request: Request, session: DbSession
) -> Me:
    """Change one's own account: the email address and notification settings. Only the
    signed-in user's own; a kind their role can't see is refused, and nothing changes."""
    user = caller.user
    assert user is not None  # noqa: S101 - guaranteed by SignedInUser
    try:
        if "email" in body.model_fields_set:
            user.email = email_address(body.email)
    except AccountError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    try:
        choose(
            session,
            user,
            (Choice(c.kind, c.channel, c.on) for c in body.notifications),
            has_requests=has_requests(session, user),
        )
    except NotChoosable as exc:
        session.rollback()
        raise forbidden(str(exc)) from exc
    session.commit()
    return me_out(request, session, user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChange, request: Request, caller: SignedInUser, session: DbSession
) -> Response:
    """Change one's own password. Other sessions of the user end; this one stays."""
    user = caller.user
    assert user is not None  # noqa: S101 - guaranteed by SignedInUser
    throttle, address = _throttle(request), _address(request)
    if throttle.blocked(user.username, address):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
    if authenticate(session, user.username, body.current_password) is None:
        throttle.failed(user.username, address)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "current password is wrong")
    try:
        set_password(session, user, body.new_password, keep=caller.session)
    except AccountError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
