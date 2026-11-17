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


def upgrade() -> None:
    # A copy synced before this reads as not gradient until the next sync replaces it.
    with op.batch_alter_table("catalog_variant", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("gradient", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("catalog_variant", schema=None) as batch_op:
        batch_op.drop_column("gradient")
