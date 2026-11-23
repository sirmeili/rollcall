"""Phone notifications: where each user's phone gets them, and the server's VAPID key pair."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from filament_tracker.db.models import Base, Device
from filament_tracker.db.types import str_enum, utcnow
from filament_tracker.domain.enums import PushRoute


class PushEndpoint(Base):
    """Where one user's phone gets its phone notifications: one per device. Only a phone with
    a user has one. A revoked or unlinked phone's is removed, and a disabled user's ignored."""

    __tablename__ = "push_endpoint"

    device_id: Mapped[str] = mapped_column(ForeignKey("device.id"), primary_key=True)
    route: Mapped[PushRoute] = mapped_column(str_enum(PushRoute, "push_route"))
    # The push service's URL for this phone.
    endpoint: Mapped[str] = mapped_column(Text)
    # The phone's Web Push keys (RFC 8291), base64url: its P-256 public key and auth secret.
    p256dh: Mapped[str | None] = mapped_column(String(128))
    auth: Mapped[str | None] = mapped_column(String(64))
    registered_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_success_at: Mapped[datetime | None]
    # Notifications given up on since the last success (or registering).
    failures: Mapped[int] = mapped_column(default=0)
    # When the first of those was given up; None while there are none.
    failing_since: Mapped[datetime | None]

    device: Mapped[Device] = relationship()

    def mark_healthy(self) -> None:
        """Clear the failures: after a success, or a new endpoint registered."""
        self.failures = 0
        self.failing_since = None


class VapidKey(Base):
    """The server's VAPID key pair (RFC 8292), made on first start and never changed: a new
    one would make every phone register again. One row. The private key is sealed with the
    settings key, like other stored secrets (ADR-0007)."""

    __tablename__ = "vapid_key"

    id: Mapped[int] = mapped_column(primary_key=True)
    private_key: Mapped[str] = mapped_column(Text)
    # The uncompressed P-256 point, base64url: what a phone registers with.
    public_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
