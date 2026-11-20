"""add request photos

Adds the request_photo table for photos of finished prints, and widens the request history
kind check for adding and removing them (#156).

Revision ID: 29efdaa213bf
Revises: 0a1c80d1b4f2
Create Date: 2026-11-20 01:24:39.048598
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "29efdaa213bf"
down_revision: str | None = "0a1c80d1b4f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = ("submitted", "edited", "priority_changed", "status_changed")
KINDS = (*KINDS_BEFORE, "photo_added", "photo_removed")


def _enum(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(*values, name="request_history_kind", native_enum=False, create_constraint=True)


def _kinds(before: Sequence[str], after: Sequence[str]) -> None:
    """Nothing points at request_history, so batch mode can copy it with foreign keys on."""
    with op.batch_alter_table("request_history", schema=None) as batch_op:
        batch_op.drop_constraint("request_history_kind", type_="check")
        batch_op.alter_column(
            "kind", existing_type=_enum(before), type_=_enum(after), existing_nullable=False
        )


def upgrade() -> None:
    op.create_table(
        "request_photo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("stored_name", sa.String(length=64), nullable=False),
        sa.Column("email_stored_name", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["print_request.id"],
            name=op.f("fk_request_photo_request_id_print_request"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["user.id"], name=op.f("fk_request_photo_uploaded_by_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_photo")),
        sa.UniqueConstraint("email_stored_name", name=op.f("uq_request_photo_email_stored_name")),
        sa.UniqueConstraint("stored_name", name=op.f("uq_request_photo_stored_name")),
    )
    with op.batch_alter_table("request_photo", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_request_photo_request_id"), ["request_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_request_photo_uploaded_by"), ["uploaded_by"], unique=False
        )
    _kinds(KINDS_BEFORE, KINDS)


def downgrade() -> None:
    # Photo entries can't be kept under the narrower check.
    op.execute("DELETE FROM request_history WHERE kind IN ('photo_added', 'photo_removed')")
    _kinds(KINDS, KINDS_BEFORE)
    with op.batch_alter_table("request_photo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_request_photo_uploaded_by"))
        batch_op.drop_index(batch_op.f("ix_request_photo_request_id"))

    op.drop_table("request_photo")
