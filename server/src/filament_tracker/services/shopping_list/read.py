"""Reading the shopping list: each product that is low on stock, has spools added by hand or
has spools on order as one item, grouped by the filament line of its catalog link, then the
products not in the catalog."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.db.models import Product
from filament_tracker.db.shopping_models import HandReason
from filament_tracker.db.shopping_models import ShoppingListItem as ItemRow
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import queries
from filament_tracker.services.catalog_links import IndexedColor, catalog_link
from filament_tracker.services.shopping_list.history import HistoryEntry, recent


@dataclass(frozen=True)
class LowStock:
    """The product is low: buying `spools` takes its Sealed count above its threshold."""

    spools: int
    sealed: int
    threshold: int


@dataclass(frozen=True)
class HandAdded:
    """Spools an Editor or Admin added by hand."""

    id: int
    spools: int
    # Who added them: None for a token, which acts for no user.
    by: str | None
    at: datetime


Reason = LowStock | HandAdded


@dataclass(frozen=True)
class ShoppingListItem:
    product: Product
    # The catalog color the product is linked to; None when it is not in the catalog.
    color: IndexedColor | None
    # Low stock first, then the hand-added reasons, oldest first.
    reasons: list[Reason]
    # Its most recent shopping list history, newest first.
    history: list[HistoryEntry] = field(default_factory=list)
    # Spools ordered and not yet arrived.
    on_order: int = 0

    @property
    def need(self) -> int:
        return sum(reason.spools for reason in self.reasons)

    @property
    def to_buy(self) -> int:
        return max(self.need - self.on_order, 0)


@dataclass(frozen=True)
class Line:
    """A filament line's items, from their products' catalog links."""

    name: str
    items: list[ShoppingListItem]

    @property
    def to_buy(self) -> int:
        return sum(item.to_buy for item in self.items)


@dataclass(frozen=True)
class ShoppingList:
    # By name.
    lines: list[Line] = field(default_factory=list)
    # Products with no catalog link, or a link to a color the catalog has dropped, last.
    not_in_catalog: list[ShoppingListItem] = field(default_factory=list)


def _low_stock(counts: queries.ProductCounts) -> LowStock | None:
    if not counts.low_stock:
        return None
    threshold = counts.product.low_stock_threshold
    sealed = counts.counts.get(SpoolState.SEALED, 0)
    return LowStock(spools=threshold - sealed + 1, sealed=sealed, threshold=threshold)


def _color(product: Product) -> IndexedColor | None:
    link = catalog_link(product)
    return link.color if link else None


def _hand_added(session: Session) -> dict[int, list[HandAdded]]:
    """Each product's hand-added reasons, oldest first."""
    found: dict[int, list[HandAdded]] = defaultdict(list)
    query = (
        select(HandReason)
        .options(selectinload(HandReason.user))
        .order_by(HandReason.at, HandReason.id)
    )
    for reason in session.scalars(query):
        by = reason.user.username if reason.user else None
        found[reason.product_id].append(HandAdded(reason.id, reason.spools, by, reason.at))
    return found


def _on_order(session: Session) -> dict[int, int]:
    """Each product's on order, where it is above 0."""
    rows = session.execute(select(ItemRow.product_id, ItemRow.on_order).where(ItemRow.on_order > 0))
    return {product_id: spools for product_id, spools in rows}


def read(session: Session) -> ShoppingList:
    """The shopping list as it stands now. Items are by product name, as on Inventory."""
    by_line: dict[str, list[ShoppingListItem]] = defaultdict(list)
    listed = ShoppingList()
    hand = _hand_added(session)
    entries = recent(session)
    on_order = _on_order(session)
    for counts in queries.inventory(session):
        product = counts.product
        low = _low_stock(counts)
        reasons: list[Reason] = [low] if low else []
        reasons += hand.get(product.id, [])
        ordered = on_order.get(product.id, 0)
        if not reasons and not ordered:
            continue
        item = ShoppingListItem(
            product, _color(product), reasons, entries.get(product.id, []), ordered
        )
        if item.color is None:
            listed.not_in_catalog.append(item)
        else:
            by_line[item.color.line].append(item)
    for name in sorted(by_line, key=str.lower):
        listed.lines.append(Line(name, by_line[name]))
    return listed
