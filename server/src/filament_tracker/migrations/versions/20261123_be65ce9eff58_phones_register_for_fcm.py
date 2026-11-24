"""phones register for FCM (#227)

A phone's push endpoint may be an FCM registration token, for phones of the google flavor.

Revision ID: be65ce9eff58
Revises: 0c3ddd2e890a
Create Date: 2026-11-23 14:02:11.511402
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "be65ce9eff58"
down_revision: str | None = "0c3ddd2e890a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROUTES_BEFORE = ("web_push",)
ROUTES = (*ROUTES_BEFORE, "fcm")


def _enum(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(*values, name="push_route", native_enum=False, create_constraint=True, length=8)


def _routes(before: Sequence[str], after: Sequence[str]) -> None:
    """Nothing points at push_endpoint, so batch mode can copy it with foreign keys on."""
    with op.batch_alter_table("push_endpoint", schema=None) as batch_op:
        batch_op.drop_constraint("push_route", type_="check")
        batch_op.alter_column(
            "route", existing_type=_enum(before), type_=_enum(after), existing_nullable=False
        )


def upgrade() -> None:
    _routes(ROUTES_BEFORE, ROUTES)


def downgrade() -> None:
    # FCM phones can't be kept under the narrower check; they register again on an upgrade.
    op.execute("DELETE FROM push_endpoint WHERE route = 'fcm'")
    _routes(ROUTES, ROUTES_BEFORE)
