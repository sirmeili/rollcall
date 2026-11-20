"""add the account email switches

Revision ID: 3f6b9d2e1c57
Revises: 0a1c80d1b4f2
Create Date: 2026-11-20 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3f6b9d2e1c57"
down_revision: str | None = "0a1c80d1b4f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # In place: a batch copy of user would drop the original, which foreign keys refuse.
    # Both on by default, for existing users too.
    op.execute("ALTER TABLE user ADD COLUMN email_on_request_change BOOLEAN DEFAULT 1 NOT NULL")
    op.execute("ALTER TABLE user ADD COLUMN email_on_new_request BOOLEAN DEFAULT 1 NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE user DROP COLUMN email_on_new_request")
    op.execute("ALTER TABLE user DROP COLUMN email_on_request_change")
