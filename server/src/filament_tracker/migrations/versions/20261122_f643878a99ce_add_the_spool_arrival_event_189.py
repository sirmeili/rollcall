"""add the spool arrival event (#189)

Revision ID: f643878a99ce
Revises: fef3b1c54d06
Create Date: 2026-11-22 00:26:40.813815
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f643878a99ce"
down_revision: str | None = "fef3b1c54d06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A plain ADD COLUMN: batch mode would copy and drop the spool table, which SQLite refuses
    # while other tables refer to it (foreign keys are on). Spools already here keep no event:
    # they were counted before anything was on order, so an undo never gives one back.
    op.add_column("spool", sa.Column("arrival_event_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE spool DROP COLUMN arrival_event_id")
