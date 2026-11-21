"""add spool holds and choice grams

Adds the spool_hold table, the grams of each filament choice, and marks request history
entries RollCall made itself, such as the move on after Approve (#161).

Revision ID: 5883d7e2d514
Revises: 7c2e5a9d4b18
Create Date: 2026-11-20 13:00:35.319100
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "5883d7e2d514"
down_revision: str | None = "7c2e5a9d4b18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spool_hold",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spool_id", sa.Integer(), nullable=False),
        sa.Column("grams", sa.Integer(), nullable=False),
        sa.Column("holder_type", sa.String(length=32), nullable=False),
        sa.Column("holder_id", sa.Integer(), nullable=False),
        sa.Column("created_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("released_at", filament_tracker.db.types.UtcDateTime(), nullable=True),
        sa.Column(
            "release_reason",
            sa.Enum(
                "done",
                "failed",
                "cancelled",
                "spool_gone",
                "changed",
                name="hold_release_reason",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["spool_id"], ["spool.id"], name=op.f("fk_spool_hold_spool_id_spool")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spool_hold")),
    )
    with op.batch_alter_table("spool_hold", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_spool_hold_holder_id"), ["holder_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_spool_hold_spool_id"), ["spool_id"], unique=False)

    with op.batch_alter_table("filament_choice", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grams", sa.Integer(), nullable=True))

    with op.batch_alter_table("request_history", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("automatic", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("request_history", schema=None) as batch_op:
        batch_op.drop_column("automatic")

    with op.batch_alter_table("filament_choice", schema=None) as batch_op:
        batch_op.drop_column("grams")

    with op.batch_alter_table("spool_hold", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spool_hold_spool_id"))
        batch_op.drop_index(batch_op.f("ix_spool_hold_holder_id"))

    op.drop_table("spool_hold")
