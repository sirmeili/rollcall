"""add the catalog

Revision ID: 06a52b9751a5
Revises: 665d59de4124
Create Date: 2026-11-16 16:39:28.233281
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "06a52b9751a5"
down_revision: str | None = "665d59de4124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_brand",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("moved_from", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("uuid", name=op.f("pk_catalog_brand")),
    )
    op.create_table(
        "catalog_sync",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column("finished_at", filament_tracker.db.types.UtcDateTime(), nullable=False),
        sa.Column(
            "result",
            sa.Enum(
                "updated",
                "not_modified",
                "failed",
                name="sync_result",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=True),
        sa.Column("etag", sa.String(length=200), nullable=True),
        sa.Column("last_modified", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_sync")),
    )
    op.create_table(
        "catalog_filament",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("brand_uuid", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("material", sa.String(length=64), nullable=False),
        sa.Column("density", sa.Float(), nullable=True),
        sa.Column("min_print_temperature", sa.Integer(), nullable=True),
        sa.Column("max_print_temperature", sa.Integer(), nullable=True),
        sa.Column("min_bed_temperature", sa.Integer(), nullable=True),
        sa.Column("max_bed_temperature", sa.Integer(), nullable=True),
        sa.Column("moved_from", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_uuid"],
            ["catalog_brand.uuid"],
            name=op.f("fk_catalog_filament_brand_uuid_catalog_brand"),
        ),
        sa.PrimaryKeyConstraint("uuid", name=op.f("pk_catalog_filament")),
    )
    with op.batch_alter_table("catalog_filament", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_catalog_filament_brand_uuid"), ["brand_uuid"], unique=False
        )

    op.create_table(
        "catalog_variant",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("filament_uuid", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("color_hex", sa.String(length=6), nullable=False),
        sa.Column("extra_hexes", sa.JSON(), nullable=False),
        sa.Column("discontinued", sa.Boolean(), nullable=False),
        sa.Column("moved_from", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["filament_uuid"],
            ["catalog_filament.uuid"],
            name=op.f("fk_catalog_variant_filament_uuid_catalog_filament"),
        ),
        sa.PrimaryKeyConstraint("uuid", name=op.f("pk_catalog_variant")),
    )
    with op.batch_alter_table("catalog_variant", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_catalog_variant_filament_uuid"), ["filament_uuid"], unique=False
        )

    op.create_table(
        "catalog_size",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("variant_uuid", sa.String(length=36), nullable=False),
        sa.Column("filament_weight", sa.Float(), nullable=False),
        sa.Column("refill", sa.Boolean(), nullable=False),
        sa.Column("article_number", sa.String(length=64), nullable=True),
        sa.Column("discontinued", sa.Boolean(), nullable=False),
        sa.Column("purchase_links", sa.JSON(), nullable=False),
        sa.Column("moved_from", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["variant_uuid"],
            ["catalog_variant.uuid"],
            name=op.f("fk_catalog_size_variant_uuid_catalog_variant"),
        ),
        sa.PrimaryKeyConstraint("uuid", name=op.f("pk_catalog_size")),
    )
    with op.batch_alter_table("catalog_size", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_catalog_size_variant_uuid"), ["variant_uuid"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("catalog_size", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_catalog_size_variant_uuid"))

    op.drop_table("catalog_size")
    with op.batch_alter_table("catalog_variant", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_catalog_variant_filament_uuid"))

    op.drop_table("catalog_variant")
    with op.batch_alter_table("catalog_filament", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_catalog_filament_brand_uuid"))

    op.drop_table("catalog_filament")
    op.drop_table("catalog_sync")
    op.drop_table("catalog_brand")
