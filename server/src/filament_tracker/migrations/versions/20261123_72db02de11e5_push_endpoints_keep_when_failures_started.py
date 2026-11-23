"""push endpoints keep when their failures started (#81)

A phone's push endpoint records when the first notification given up since its last success
was, as well as how many there have been.

Revision ID: 72db02de11e5
Revises: be65ce9eff58
Create Date: 2026-11-23 13:38:17.108543
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import filament_tracker.db.types

revision: str = "72db02de11e5"
down_revision: str | None = "be65ce9eff58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("push_endpoint", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("failing_since", filament_tracker.db.types.UtcDateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("push_endpoint", schema=None) as batch_op:
        batch_op.drop_column("failing_since")
