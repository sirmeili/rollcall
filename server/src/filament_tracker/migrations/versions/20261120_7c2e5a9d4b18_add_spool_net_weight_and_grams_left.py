"""add spool net weight and grams left

Revision ID: 7c2e5a9d4b18
Revises: 29efdaa213bf
Create Date: 2026-11-20 18:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c2e5a9d4b18"
down_revision: str | None = "29efdaa213bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copied, not imported: a migration keeps the rule it was written with.
FALLBACK_NET_WEIGHT_G = 1000


def upgrade() -> None:
    # In place: a batch copy of spool would drop the original, which foreign keys refuse.
    op.execute("ALTER TABLE spool ADD COLUMN net_weight_g INTEGER")
    op.execute("ALTER TABLE spool ADD COLUMN grams_left_g INTEGER")
    _fill(op.get_bind())


def _fill(connection: sa.Connection) -> None:
    """Net weight from the spool's tag, else its catalog color's size weight when all its
    sizes weigh the same, else 1000 g.
    Grams left: the net weight when Sealed, net weight x remaining % when Open with one,
    otherwise unknown."""
    sizes: dict[str, set[float]] = {}
    for color, weight in connection.execute(
        sa.text("SELECT variant_uuid, filament_weight FROM catalog_size")
    ):
        sizes.setdefault(color, set()).add(weight)
    tag_weights: dict[int, int] = {}
    for spool_id, decoded in connection.execute(
        sa.text(
            "SELECT spool_id, decoded_json FROM tag WHERE spool_id IS NOT NULL"
            " AND decoded_json IS NOT NULL ORDER BY first_seen_at, id"
        )
    ):
        weight = json.loads(decoded).get("spool_weight_g")
        if isinstance(weight, int) and weight > 0:
            tag_weights.setdefault(spool_id, weight)
    spools = connection.execute(
        sa.text(
            "SELECT spool.id, spool.state, spool.remaining_pct,"
            " COALESCE(product.catalog_manual_uuid, product.catalog_auto_uuid)"
            " FROM spool JOIN product ON product.id = spool.product_id"
        )
    ).all()
    for spool_id, state, pct, color in spools:
        net = tag_weights.get(spool_id)
        if net is None:
            # Several sizes of one weight still give one weight.
            own = sizes.get(color or "", set())
            net = round(next(iter(own))) if len(own) == 1 else FALLBACK_NET_WEIGHT_G
        left = None
        if state == "sealed":
            left = net
        elif state == "open" and pct is not None:
            left = round(net * pct / 100)
        connection.execute(
            sa.text("UPDATE spool SET net_weight_g = :net, grams_left_g = :left WHERE id = :id"),
            {"net": net, "left": left, "id": spool_id},
        )


def downgrade() -> None:
    op.execute("ALTER TABLE spool DROP COLUMN grams_left_g")
    op.execute("ALTER TABLE spool DROP COLUMN net_weight_g")
