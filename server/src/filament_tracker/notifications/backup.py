"""Backup failed: the notification each Admin who chose it gets when a nightly backup fails,
with the error's one-line reason, about the Settings page."""

from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.domain.enums import NotificationKind
from filament_tracker.notifications.notification import Notification
from filament_tracker.notifications.notifier import Notifier

BACKUP_FAILED_SUBJECT = "Backup failed"
BACKUP_FAILED_SENTENCE = "Last night's backup failed: {reason}."
OPEN_SETTINGS = "Open Settings"


def backup_failed(reason: str) -> Notification:
    """Nobody did it, so nobody is left out for having done it."""
    return Notification(
        NotificationKind.BACKUP_FAILED,
        subject=BACKUP_FAILED_SUBJECT,
        sentence=BACKUP_FAILED_SENTENCE.format(reason=reason),
        path="/settings",
        link_text=OPEN_SETTINGS,
    )


def backup_failed_sender(
    sessions: sessionmaker[Session], notifier: Notifier
) -> Callable[[str], None]:
    """What the backup job calls with the reason when a backup fails."""

    def send(reason: str) -> None:
        with sessions() as session:
            notifier.send(session, lambda: [backup_failed(reason)])

    return send
