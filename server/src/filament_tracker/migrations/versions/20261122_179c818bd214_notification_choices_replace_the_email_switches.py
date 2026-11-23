"""notification choices replace the account email switches (#218)

A switch that was off becomes an off choice for each kind it covered: "emails about my
requests" for Request update and New photo, "new request" for New request. A switch that
was on stores nothing, since the default matches it.

Revision ID: 179c818bd214
Revises: f643878a99ce
Create Date: 2026-11-22 22:38:25.984979
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "179c818bd214"
down_revision: str | None = "f643878a99ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# An off choice for each kind a switch that was off covered.
OFF_CHOICES = (
    """INSERT INTO notification_choice (user_id, kind, channel, "on")
    SELECT id, 'request_update', 'email', 0 FROM user WHERE email_on_request_change = 0""",
    """INSERT INTO notification_choice (user_id, kind, channel, "on")
    SELECT id, 'new_photo', 'email', 0 FROM user WHERE email_on_request_change = 0""",
    """INSERT INTO notification_choice (user_id, kind, channel, "on")
    SELECT id, 'new_request', 'email', 0 FROM user WHERE email_on_new_request = 0""",
)
# Back again: a switch is off if any kind it covered was chosen off.
SWITCHES_OFF = (
    """UPDATE user SET email_on_request_change = 0 WHERE id IN (
    SELECT user_id FROM notification_choice
    WHERE channel = 'email' AND "on" = 0 AND kind IN ('request_update', 'new_photo'))""",
    """UPDATE user SET email_on_new_request = 0 WHERE id IN (
    SELECT user_id FROM notification_choice
    WHERE channel = 'email' AND "on" = 0 AND kind = 'new_request')""",
)


def upgrade() -> None:
    op.create_table(
        "notification_choice",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "new_request",
                "request_update",
                "new_photo",
                "low_stock",
                "suggestion",
                "nearly_out",
                "backup_failed",
                name="notification_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum(
                "email", name="notification_channel", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("on", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_notification_choice_user_id_user")
        ),
        sa.PrimaryKeyConstraint("user_id", "kind", "channel", name=op.f("pk_notification_choice")),
    )
    for statement in OFF_CHOICES:
        op.execute(statement)
    # In place: a batch copy of user would drop the original, which foreign keys refuse.
    op.execute("ALTER TABLE user DROP COLUMN email_on_request_change")
    op.execute("ALTER TABLE user DROP COLUMN email_on_new_request")


def downgrade() -> None:
    op.execute("ALTER TABLE user ADD COLUMN email_on_request_change BOOLEAN DEFAULT 1 NOT NULL")
    op.execute("ALTER TABLE user ADD COLUMN email_on_new_request BOOLEAN DEFAULT 1 NOT NULL")
    for statement in SWITCHES_OFF:
        op.execute(statement)
    op.drop_table("notification_choice")
