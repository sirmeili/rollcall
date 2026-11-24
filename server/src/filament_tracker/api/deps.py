"""Shared request dependencies."""

from collections.abc import Callable, Iterable, Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from filament_tracker.mail.sender import MailSender
from filament_tracker.notifications.notification import Notification
from filament_tracker.notifications.notifier import Notifier


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request; the route commits what it changes."""
    with request.app.state.session_factory() as session:
        yield session


def mail_sender(request: Request) -> MailSender:
    """The app's background mail sender."""
    return request.app.state.mail


def notify_after_commit(
    request: Request, session: Session, build: Callable[[], Iterable[Notification]]
) -> None:
    """Build the notifications once the change has committed and hand them to the
    background senders, by email and to phones. Links in emails use PUBLIC_URL only, never
    this request's Host header."""
    notifier: Notifier = request.app.state.notifier
    notifier.send(session, build)
