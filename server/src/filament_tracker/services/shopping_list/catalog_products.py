"""The product for a catalog color: the product linked to it if one is, otherwise a new
provisional product made from it ("From the catalog"), linked to it by hand by the person
putting it on the list. The first scan of its tag fills it in."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import CatalogFilament, CatalogVariant
from filament_tracker.db.models import Product
from filament_tracker.services.catalog_links import UnknownColor, linked_product, set_manual


def product_for_color(session: Session, uuid: str, user_id: int | None, now: datetime) -> Product:
    """The product linked to the catalog color, or a new "From the catalog" one, named, typed
    and colored from the color and its filament line. A color not in the catalog is refused
    (UnknownColor)."""
    linked = linked_product(session, uuid)
    if linked is not None:
        return linked
    found = session.execute(
        select(CatalogVariant, CatalogFilament)
        .join(CatalogFilament, CatalogVariant.filament_uuid == CatalogFilament.uuid)
        .where(CatalogVariant.uuid == uuid)
    ).one_or_none()
    if found is None:
        raise UnknownColor(uuid)
    color, line = found
    made = Product(
        filament_type=line.material,
        color_rgba=f"{color.color_hex.upper()}FF",
        display_name=f"{color.name} {line.name}"[:100],
        provisional=True,
        from_catalog=True,
    )
    session.add(made)
    session.flush()
    set_manual(session, made, uuid, user_id, now)
    return made
