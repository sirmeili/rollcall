"""add user email addresses

Revision ID: 0a1c80d1b4f2
Revises: edd3e5a79906
Create Date: 2026-11-19 23:35:40.636662
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0a1c80d1b4f2"
down_revision: str | None = "edd3e5a79906"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # In place: a batch copy of user would drop the original, which foreign keys refuse.
    op.execute("ALTER TABLE user ADD COLUMN email VARCHAR(254)")


def downgrade() -> None:
    op.execute("ALTER TABLE user DROP COLUMN email")
