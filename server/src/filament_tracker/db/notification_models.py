"""Notification settings: only the choices users made are stored. No row for a user, kind
and channel means the kind's default applies (notifications/kinds.py)."""

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from filament_tracker.db.models import Base
from filament_tracker.db.types import str_enum
from filament_tracker.domain.enums import Channel, NotificationKind


class NotificationChoice(Base):
    """A user's own choice to get, or not get, one kind of notification on one channel. Kept
    when their role changes, so it applies again if the role changes back."""

    __tablename__ = "notification_choice"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    kind: Mapped[NotificationKind] = mapped_column(
        str_enum(NotificationKind, "notification_kind"), primary_key=True
    )
    channel: Mapped[Channel] = mapped_column(
        str_enum(Channel, "notification_channel"), primary_key=True
    )
    on: Mapped[bool] = mapped_column(Boolean)
