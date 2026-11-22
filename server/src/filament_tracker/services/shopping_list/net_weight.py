"""The size an item turns print requests' grams into spools with, first of: the size chosen
on the item; the net weight of the product's most recently received spool; its catalog
color's 1000 g size (refill or not), else its only size, else its smallest; 1000 g."""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import CatalogSize
from filament_tracker.db.models import Product, Spool
from filament_tracker.db.shopping_models import ShoppingListItem
from filament_tracker.services.catalog_links import IndexedColor
from filament_tracker.services.grams import FALLBACK_NET_WEIGHT_G


class SizeFrom(StrEnum):
    """Where an item's size came from."""

    CHOSEN = "chosen"
    LAST_SPOOL = "last_spool"
    CATALOG = "catalog"
    DEFAULT = "default"


@dataclass(frozen=True)
class NetWeight:
    grams: int
    source: SizeFrom


def _last_spool(session: Session, product: Product) -> int | None:
    return session.scalar(
        select(Spool.net_weight_g)
        .where(
            Spool.product_id == product.id,
            Spool.received_at.is_not(None),
            Spool.net_weight_g.is_not(None),
        )
        .order_by(Spool.received_at.desc(), Spool.id.desc())
        .limit(1)
    )


def _catalog(session: Session, color: IndexedColor) -> int | None:
    weights = set(
        session.scalars(
            select(CatalogSize.filament_weight).where(CatalogSize.variant_uuid == color.uuid)
        )
    )
    if not weights:
        return None
    return FALLBACK_NET_WEIGHT_G if FALLBACK_NET_WEIGHT_G in weights else round(min(weights))


def net_weight(session: Session, product: Product, color: IndexedColor | None) -> NetWeight:
    """The item's size; `color` is the catalog color the product is linked to, if any."""
    chosen = session.scalar(
        select(ShoppingListItem.chosen_size_g).where(ShoppingListItem.product_id == product.id)
    )
    if chosen is not None:
        return NetWeight(chosen, SizeFrom.CHOSEN)
    last = _last_spool(session, product)
    if last is not None:
        return NetWeight(last, SizeFrom.LAST_SPOOL)
    sized = _catalog(session, color) if color else None
    if sized is not None:
        return NetWeight(sized, SizeFrom.CATALOG)
    return NetWeight(FALLBACK_NET_WEIGHT_G, SizeFrom.DEFAULT)
