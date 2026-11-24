"""name linked products after their catalog color (#263)

A product already linked to a catalog color that still has its default name takes its
catalog name. The default-name test and the catalog-name rule are copied here, as
migrations don't import app code.

Revision ID: e41f7a2c9b63
Revises: 72db02de11e5
Create Date: 2026-11-24 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e41f7a2c9b63"
down_revision: str | None = "72db02de11e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# product.display_name's length.
NAME_LENGTH = 100


def _is_default_name(name: str, color_rgba: str) -> bool:
    """Whether a name ends with " #" and the color's hex digits, whatever their case."""
    return name.casefold().endswith(f" #{color_rgba[:6]}".casefold())


def upgrade() -> None:
    connection = op.get_bind()
    catalog_names = {
        uuid: f"{color} {line}"[:NAME_LENGTH]
        for uuid, color, line in connection.execute(
            sa.text(
                "SELECT catalog_variant.uuid, catalog_variant.name, catalog_filament.name"
                " FROM catalog_variant JOIN catalog_filament"
                " ON catalog_filament.uuid = catalog_variant.filament_uuid"
            )
        )
    }
    products = connection.execute(
        sa.text(
            "SELECT id, display_name, color_rgba, catalog_manual_uuid, catalog_auto_uuid"
            " FROM product WHERE catalog_manual_uuid IS NOT NULL"
            " OR catalog_auto_uuid IS NOT NULL"
        )
    ).all()
    for id_, name, color_rgba, manual, auto in products:
        # The effective link: the manual one if set, otherwise the automatic one. A manual
        # link to a color no longer in the catalog gives none.
        catalog_name = catalog_names.get(manual or auto)
        if catalog_name is not None and _is_default_name(name, color_rgba):
            connection.execute(
                sa.text("UPDATE product SET display_name = :name WHERE id = :id"),
                {"name": catalog_name, "id": id_},
            )


def downgrade() -> None:
    # The default names are not kept, and a catalog name is a name like any other.
    pass
