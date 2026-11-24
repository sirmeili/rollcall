"""add phone notifications (#224)

The Phone channel in the notification settings, each phone's push endpoint, and the
server's VAPID key pair.

Revision ID: 0c3ddd2e890a
Revises: 179c818bd214
Create Date: 2026-11-23 10:26:47.353180
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "0c3ddd2e890a"
down_revision: str | None = "179c818bd214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNELS_BEFORE = ("email",)
CHANNELS = (*CHANNELS_BEFORE, "phone")


def _enum(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(*values, name="notification_channel", native_enum=False, create_constraint=True)


def _channels(before: Sequence[str], after: Sequence[str]) -> None:
    """Nothing points at notification_choice, so batch mode can copy it with foreign keys
    on."""
    with op.batch_alter_table("notification_choice", schema=None) as batch_op:
        batch_op.drop_constraint("notification_channel", type_="check")
        batch_op.alter_column(
            "channel", existing_type=_enum(before), type_=_enum(after), existing_nullable=False
        )


def upgrade() -> None:
    _channels(CHANNELS_BEFORE, CHANNELS)
    op.create_table(
        "vapid_key",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("private_key", sa.Text(), nullable=False),
        sa.Column("public_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vapid_key")),
    )
    op.create_table(
        "push_endpoint",
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column(
            "route",
            sa.Enum("web_push", name="push_route", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=128), nullable=True),
        sa.Column("auth", sa.String(length=64), nullable=True),
        sa.Column("registered_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("last_success_at", filament_tracker.db.types.UtcDateTime(), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["device.id"], name=op.f("fk_push_endpoint_device_id_device")
        ),
        sa.PrimaryKeyConstraint("device_id", name=op.f("pk_push_endpoint")),
    )


def downgrade() -> None:
    op.drop_table("push_endpoint")
    op.drop_table("vapid_key")
    # Phone choices can't be kept under the narrower check.
    op.execute("DELETE FROM notification_choice WHERE channel = 'phone'")
    _channels(CHANNELS, CHANNELS_BEFORE)
