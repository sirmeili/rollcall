"""add requesters and print requests

Revision ID: 8be4824dafad
Revises: 5b8e1c7d2a94
Create Date: 2026-11-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "8be4824dafad"
down_revision: str | None = "5b8e1c7d2a94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "print_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("needed_by", sa.Date(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum(
                "urgent",
                "normal",
                "no_rush",
                name="request_priority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("link", sa.String(length=2000), nullable=True),
        sa.Column(
            "status",
            sa.Enum("submitted", name="request_status", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("file_stored_name", sa.String(length=64), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "file_kind",
            sa.Enum(
                "3mf", "stl", name="model_file_kind", native_enum=False, create_constraint=True
            ),
            nullable=True,
        ),
        sa.Column("created_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["user.id"], name=op.f("fk_print_request_requester_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_print_request")),
    )
    with op.batch_alter_table("print_request", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_print_request_requester_id"), ["requester_id"], unique=False
        )

    op.create_table(
        "request_upload",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stored_name", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "3mf", "stl", name="upload_file_kind", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("created_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_request_upload_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_upload")),
        sa.UniqueConstraint("stored_name", name=op.f("uq_request_upload_stored_name")),
    )
    with op.batch_alter_table("request_upload", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_request_upload_user_id"), ["user_id"], unique=False)

    op.create_table(
        "filament_choice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("catalog_uuid", sa.String(length=36), nullable=True),
        sa.Column("catalog_line", sa.String(length=200), nullable=True),
        sa.Column("catalog_name", sa.String(length=200), nullable=True),
        sa.Column("catalog_hexes", sa.JSON(), nullable=True),
        sa.Column("note", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "(product_id IS NULL) <> (catalog_uuid IS NULL)",
            name=op.f("ck_filament_choice_product_or_catalog_color"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_filament_choice_product_id_product")
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["print_request.id"],
            name=op.f("fk_filament_choice_request_id_print_request"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_filament_choice")),
    )
    with op.batch_alter_table("filament_choice", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_filament_choice_request_id"), ["request_id"], unique=False
        )

    op.create_table(
        "request_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "submitted",
                "edited",
                "priority_changed",
                name="request_history_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=True),
        sa.Column("from_value", sa.String(length=32), nullable=True),
        sa.Column("to_value", sa.String(length=32), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["print_request.id"],
            name=op.f("fk_request_history_request_id_print_request"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_request_history_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_history")),
    )
    with op.batch_alter_table("request_history", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_request_history_request_id"), ["request_id"], unique=False
        )

    # In place: a batch copy of user would drop the original, which foreign keys refuse.
    op.execute("ALTER TABLE user ADD COLUMN requester BOOLEAN DEFAULT 0 NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE user DROP COLUMN requester")

    with op.batch_alter_table("request_history", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_request_history_request_id"))

    op.drop_table("request_history")
    with op.batch_alter_table("filament_choice", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_filament_choice_request_id"))

    op.drop_table("filament_choice")
    with op.batch_alter_table("request_upload", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_request_upload_user_id"))

    op.drop_table("request_upload")
    with op.batch_alter_table("print_request", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_print_request_requester_id"))

    op.drop_table("print_request")
