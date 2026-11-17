"""add catalog links and BambuStudio's color codes

Revision ID: 5b8e1c7d2a94
Revises: d02002b943bd
Create Date: 2026-11-17 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b8e1c7d2a94"
down_revision: str | None = "d02002b943bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# product and catalog_sync are altered in place. Batch mode would copy product and drop the
# original, which foreign keys refuse while spools point at it.
PRODUCT_COLUMNS = (
    "catalog_auto_uuid VARCHAR(36)",
    "catalog_manual_uuid VARCHAR(36)",
    "catalog_manual_by INTEGER",
    "catalog_manual_at DATETIME",
    "catalog_manual_line VARCHAR(200)",
    "catalog_manual_name VARCHAR(200)",
)


def upgrade() -> None:
    op.create_table(
        "bambu_color_code",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bambu_code", sa.String(length=16), nullable=False),
        sa.Column("filament_id", sa.String(length=16), nullable=False),
        sa.Column("color_code", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bambu_color_code")),
    )
    # Every sync recorded so far was OFDB's.
    op.execute(
        "ALTER TABLE catalog_sync ADD COLUMN source VARCHAR(11) DEFAULT 'ofdb' NOT NULL"
        " CONSTRAINT ck_catalog_sync_catalog_source CHECK (source IN ('ofdb', 'bambustudio'))"
    )
    for column in PRODUCT_COLUMNS:
        op.execute(f"ALTER TABLE product ADD COLUMN {column}")


def downgrade() -> None:
    # SQLite 3.35 and later drop a column in place, but not one with a CHECK constraint:
    # catalog_sync's goes with a batch copy, which no foreign key points at.
    with op.batch_alter_table("catalog_sync") as batch_op:
        batch_op.drop_constraint(op.f("ck_catalog_sync_catalog_source"), type_="check")
        batch_op.drop_column("source")
    for column in reversed(PRODUCT_COLUMNS):
        op.execute(f"ALTER TABLE product DROP COLUMN {column.split()[0]}")
    op.drop_table("bambu_color_code")
