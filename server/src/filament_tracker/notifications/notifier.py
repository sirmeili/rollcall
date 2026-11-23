"""Sending notifications on every channel, after the change that caused them committed.

The emails (while email is on) and the phone notifications are built from the committed
change and handed to their background senders, so nothing waits for a mail server or a push
service. Nothing here ever fails the change: a notification that can't be built is logged and
dropped.
"""

import logging
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from filament_tracker.mail.sender import MailSender
from filament_tracker.notifications.email import emails
from filament_tracker.notifications.notification import Notification
from filament_tracker.notifications.phone import phone_pushes
from filament_tracker.push.sender import PushSender

logger = logging.getLogger(__name__)


class Notifier:
    """`public_url` reads PUBLIC_URL, which links in emails use, when they are built."""

    def __init__(
        self, mail: MailSender, phones: PushSender, public_url: Callable[[], str | None]
    ) -> None:
        self._mail = mail
        self._phones = phones
        self._public_url = public_url

    def send(self, session: Session, build: Callable[[], Iterable[Notification]]) -> None:
        """Build the notifications with `session` and hand them to the senders."""
        try:
            notifications = list(build())
            if not notifications:
                return
            if self._mail.on:
                self._mail.send_later(emails(session, notifications, self._public_url()))
            self._phones.send_later(phone_pushes(session, notifications))
        except Exception as error:
            # Only the type: the error's text could hold anything.
            logger.warning("notifications: unexpected %s while building them", type(error).__name__)
