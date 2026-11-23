"""A user's notification settings: read, and changed only by that user."""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.notification_models import NotificationChoice
from filament_tracker.domain.enums import Channel, NotificationKind
from filament_tracker.notifications.kinds import KINDS, default, may_choose

NOT_YOURS_TO_CHOOSE = "you can't choose that notification"


class NotChoosable(Exception):
    """A kind the user's role can't see."""


@dataclass(frozen=True)
class Setting:
    kind: NotificationKind
    channel: Channel
    on: bool
    # No choice is stored: the default applies.
    default: bool


@dataclass(frozen=True)
class Choice:
    kind: NotificationKind
    channel: Channel
    on: bool


def notification_settings(session: Session, user: User) -> list[Setting]:
    """The user's setting for each kind they may choose, on each channel, in kind order."""
    chosen = {
        (row.kind, row.channel): row.on
        for row in session.scalars(
            select(NotificationChoice).where(NotificationChoice.user_id == user.id)
        )
    }
    settings = []
    for kind in KINDS:
        if not may_choose(user, kind):
            continue
        for channel in Channel:
            on = chosen.get((kind, channel))
            if on is None:
                settings.append(Setting(kind, channel, default(user, kind, channel), True))
            else:
                settings.append(Setting(kind, channel, on, False))
    return settings


def choose(session: Session, user: User, choices: Iterable[Choice]) -> None:
    """Store the user's own choices. Refuses them all if any is a kind they can't see."""
    choices = list(choices)
    if not all(may_choose(user, c.kind) for c in choices):
        raise NotChoosable(NOT_YOURS_TO_CHOOSE)
    for choice in choices:
        session.merge(
            NotificationChoice(
                user_id=user.id, kind=choice.kind, channel=choice.channel, on=choice.on
            )
        )
