"""mark gradient catalog colors

Revision ID: d02002b943bd
Revises: 06a52b9751a5
Create Date: 2026-11-16 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d02002b943bd"
down_revision: str | None = "06a52b9751a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Both directions alter catalog_variant in place. Batch mode would copy the table and drop
# the original, which foreign keys refuse while catalog_size rows point at it.


def upgrade() -> None:
    # A copy synced before this reads as not gradient until the next sync replaces it. A
    # plain "0" default, not sa.false(), lets SQLite add the column without a copy.
    op.add_column(
        "catalog_variant",
        sa.Column("gradient", sa.Boolean(), server_default="0", nullable=False),
    )
    # Forget what was downloaded, so the next sync fetches the export in full and fills in
    # the flag, rather than hearing "not modified" until OFDB publishes something new.
    op.execute("UPDATE catalog_sync SET etag = NULL, last_modified = NULL")


def downgrade() -> None:
    # SQLite 3.35 and later drop a column in place.
    op.execute("ALTER TABLE catalog_variant DROP COLUMN gradient")
