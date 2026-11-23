"""Backup failed: the email each Admin who chose it is sent when a nightly backup fails, with
the error's one-line reason and a link to Settings (built from PUBLIC_URL only)."""

from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.domain.enums import NotificationKind
from filament_tracker.mail.message import Email
from filament_tracker.mail.sender import MailSender
from filament_tracker.notifications.email import compose
from filament_tracker.notifications.recipients import email_recipients

BACKUP_FAILED_SUBJECT = "Backup failed"
BACKUP_FAILED_SENTENCE = "Last night's backup failed: {reason}."
OPEN_SETTINGS = "Open Settings"


def backup_failed_emails(session: Session, reason: str, public_url: str | None) -> list[Email]:
    """One email to each person told about a failed backup. Nobody did it, so nobody is left
    out for having done it."""
    link = None if public_url is None else f"{public_url}/settings"
    return [
        compose(
            to,
            subject=BACKUP_FAILED_SUBJECT,
            sentence=BACKUP_FAILED_SENTENCE.format(reason=reason),
            link=link,
            link_text=OPEN_SETTINGS,
        )
        for to in email_recipients(session, NotificationKind.BACKUP_FAILED, actor=None)
    ]


def backup_failed_sender(
    sessions: sessionmaker[Session], mail: MailSender, public_url: Callable[[], str | None]
) -> Callable[[str], None]:
    """What the backup job calls with the reason when a backup fails: the emails are built and
    handed to the background sender, and nothing is built while email is off."""

    def send(reason: str) -> None:
        if not mail.on:
            return
        with sessions() as session:
            emails = backup_failed_emails(session, reason, public_url())
        mail.send_later(emails)

    return send
