"""Shared request dependencies."""

from collections.abc import Callable, Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from filament_tracker.mail.message import Email
from filament_tracker.mail.sender import MailSender


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request; the route commits what it changes."""
    with request.app.state.session_factory() as session:
        yield session


def mail_sender(request: Request) -> MailSender:
    """The app's background mail sender."""
    return request.app.state.mail


def _public_url(request: Request) -> str | None:
    """Where emails link to: PUBLIC_URL only, never this request's Host header."""
    return request.app.state.settings_store.text("public_url")


def send_after_commit(request: Request, build: Callable[[str | None], list[Email]]) -> None:
    """Build the emails once the change has committed, from the public URL, and hand them to
    the background sender; nothing is built while email is off."""
    mail = mail_sender(request)
    if mail.on:
        mail.send_later(build(_public_url(request)))
