"""add the request pipeline statuses

Widens the request status and request history kind checks for the pipeline (#76). Existing
requests stay Submitted.

Revision ID: edd3e5a79906
Revises: 8be4824dafad
Create Date: 2026-11-19 23:36:05.667228
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "edd3e5a79906"
down_revision: str | None = "8be4824dafad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES_BEFORE = ("submitted",)
STATUSES = (
    "submitted",
    "approved",
    "waiting_on_filament",
    "queued",
    "printing",
    "done",
    "picked_up",
    "rejected",
    "cancelled",
    "failed",
)
KINDS_BEFORE = ("submitted", "edited", "priority_changed")
KINDS = (*KINDS_BEFORE, "status_changed")


def _enum(values: Sequence[str], name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _change(
    table: str, column: str, name: str, before: Sequence[str], after: Sequence[str]
) -> None:
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.drop_constraint(name, type_="check")
        batch_op.alter_column(
            column,
            existing_type=_enum(before, name),
            type_=_enum(after, name),
            existing_nullable=False,
        )


def _foreign_keys_off() -> None:
    """SQLite can't change a CHECK constraint in place, so batch mode copies print_request
    and drops the original, which filament choices and history entries point at. As SQLite's
    own recipe for such changes says, foreign keys go off first, outside a transaction (where
    the pragma would do nothing), and are checked once the copy has the original's name."""
    connection = op.get_bind().connection.dbapi_connection
    if connection.in_transaction:
        connection.commit()
    op.execute("PRAGMA foreign_keys = OFF")


def _foreign_keys_checked() -> None:
    broken = op.get_bind().exec_driver_sql("PRAGMA foreign_key_check").all()
    if broken:
        raise RuntimeError(f"foreign keys broken by the copy: {broken}")


def upgrade() -> None:
    _foreign_keys_off()
    _change("print_request", "status", "request_status", STATUSES_BEFORE, STATUSES)
    _change("request_history", "kind", "request_history_kind", KINDS_BEFORE, KINDS)
    _foreign_keys_checked()


def downgrade() -> None:
    _foreign_keys_off()
    # Requests and history entries past Submitted can't be kept under the narrower checks.
    op.execute("DELETE FROM request_history WHERE kind = 'status_changed'")
    op.execute("UPDATE print_request SET status = 'submitted'")
    _change("request_history", "kind", "request_history_kind", KINDS, KINDS_BEFORE)
    _change("print_request", "status", "request_status", STATUSES, STATUSES_BEFORE)
    _foreign_keys_checked()
