"""add the shopping list tables

Every table and column the shopping list (#78) stores, laid down at once so the tickets
building on it need no migrations of their own: items, hand-added reasons, suggestions, the
shopping list history, possible duplicates and their candidates, products' "from the
catalog" marker and each spool's arrival-counted flag.

Revision ID: fef3b1c54d06
Revises: 9d41c6b7e2a3
Create Date: 2026-11-21 23:34:37.965585
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "fef3b1c54d06"
down_revision: str | None = "9d41c6b7e2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "possible_duplicate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "open",
                "same_product",
                "kept_separate",
                name="duplicate_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", filament_tracker.db.types.UtcDateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["user.id"], name=op.f("fk_possible_duplicate_decided_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_possible_duplicate_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_possible_duplicate")),
    )
    with op.batch_alter_table("possible_duplicate", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_possible_duplicate_product_id"), ["product_id"], unique=False
        )

    op.create_table(
        "shopping_hand_reason",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("spools", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_shopping_hand_reason_product_id_product")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_shopping_hand_reason_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_hand_reason")),
    )
    with op.batch_alter_table("shopping_hand_reason", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_shopping_hand_reason_product_id"), ["product_id"], unique=False
        )

    op.create_table(
        "shopping_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "added_by_hand",
                "removed_by_hand",
                "suggested",
                "suggestion_added",
                "suggestion_dismissed",
                "ordered",
                "on_order_changed",
                "dismissed",
                "brought_back",
                "size_changed",
                "same_product",
                name="shopping_action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("spools", sa.Integer(), nullable=True),
        sa.Column("size_g", sa.Integer(), nullable=True),
        sa.Column("on_order", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_shopping_history_product_id_product")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_shopping_history_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_history")),
    )
    with op.batch_alter_table("shopping_history", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_shopping_history_product_id"), ["product_id"], unique=False
        )

    op.create_table(
        "shopping_list_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("on_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chosen_size_g", sa.Integer(), nullable=True),
        sa.Column("dismissed_need", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_shopping_list_item_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_list_item")),
        sa.UniqueConstraint("product_id", name=op.f("uq_shopping_list_item_product_id")),
    )
    op.create_table(
        "shopping_suggestion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("catalog_uuid", sa.String(length=36), nullable=True),
        sa.Column("spools", sa.Integer(), nullable=False),
        sa.Column("suggested_by", sa.Integer(), nullable=True),
        sa.Column("suggested_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "added",
                "dismissed",
                name="suggestion_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", filament_tracker.db.types.UtcDateTime(), nullable=True),
        sa.CheckConstraint(
            "(product_id IS NULL) != (catalog_uuid IS NULL)",
            name=op.f("ck_shopping_suggestion_product_or_catalog_color"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["user.id"], name=op.f("fk_shopping_suggestion_decided_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_shopping_suggestion_product_id_product")
        ),
        sa.ForeignKeyConstraint(
            ["suggested_by"], ["user.id"], name=op.f("fk_shopping_suggestion_suggested_by_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_suggestion")),
    )
    with op.batch_alter_table("shopping_suggestion", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_shopping_suggestion_product_id"), ["product_id"], unique=False
        )

    op.create_table(
        "possible_duplicate_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("duplicate_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["duplicate_id"],
            ["possible_duplicate.id"],
            name=op.f("fk_possible_duplicate_candidate_duplicate_id_possible_duplicate"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_possible_duplicate_candidate_product_id_product"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_possible_duplicate_candidate")),
        sa.UniqueConstraint(
            "duplicate_id", "product_id", name=op.f("uq_possible_duplicate_candidate_duplicate_id")
        ),
    )
    with op.batch_alter_table("possible_duplicate_candidate", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_possible_duplicate_candidate_duplicate_id"),
            ["duplicate_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_possible_duplicate_candidate_product_id"), ["product_id"], unique=False
        )

    # Plain ADD COLUMNs: batch mode would copy and drop the product and spool tables, which
    # SQLite refuses while other tables refer to them (foreign keys are on).
    op.add_column(
        "product",
        sa.Column("from_catalog", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "spool",
        sa.Column("arrival_counted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    # Spools already here have arrived: nothing was on order for them, so a later undo or
    # placeholder link never changes on order.
    op.execute("UPDATE spool SET arrival_counted = 1")


def downgrade() -> None:
    op.execute("ALTER TABLE spool DROP COLUMN arrival_counted")
    op.execute("ALTER TABLE product DROP COLUMN from_catalog")

    with op.batch_alter_table("possible_duplicate_candidate", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_possible_duplicate_candidate_product_id"))
        batch_op.drop_index(batch_op.f("ix_possible_duplicate_candidate_duplicate_id"))

    op.drop_table("possible_duplicate_candidate")
    with op.batch_alter_table("shopping_suggestion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_shopping_suggestion_product_id"))

    op.drop_table("shopping_suggestion")
    op.drop_table("shopping_list_item")
    with op.batch_alter_table("shopping_history", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_shopping_history_product_id"))

    op.drop_table("shopping_history")
    with op.batch_alter_table("shopping_hand_reason", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_shopping_hand_reason_product_id"))

    op.drop_table("shopping_hand_reason")
    with op.batch_alter_table("possible_duplicate", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_possible_duplicate_product_id"))

    op.drop_table("possible_duplicate")
