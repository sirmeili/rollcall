"""add the holds changed history kind

Widens the request history kind check for an Admin changing a request's holds by hand
(#165).

Revision ID: 9d41c6b7e2a3
Revises: 5883d7e2d514
Create Date: 2026-11-20 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d41c6b7e2a3"
down_revision: str | None = "5883d7e2d514"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = (
    "submitted",
    "edited",
    "priority_changed",
    "status_changed",
    "photo_added",
    "photo_removed",
)
KINDS = (*KINDS_BEFORE, "holds_changed")


def _enum(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(*values, name="request_history_kind", native_enum=False, create_constraint=True)


def _kinds(before: Sequence[str], after: Sequence[str]) -> None:
    """Nothing points at request_history, so batch mode can copy it with foreign keys on."""
    with op.batch_alter_table("request_history", schema=None) as batch_op:
        batch_op.drop_constraint("request_history_kind", type_="check")
        batch_op.alter_column(
            "kind", existing_type=_enum(before), type_=_enum(after), existing_nullable=False
        )


def upgrade() -> None:
    _kinds(KINDS_BEFORE, KINDS)


def downgrade() -> None:
    # Hold change entries can't be kept under the narrower check.
    op.execute("DELETE FROM request_history WHERE kind = 'holds_changed'")
    _kinds(KINDS, KINDS_BEFORE)
