"""Reading the shopping list: each product that is low on stock, that print requests are
short of, that has spools added by hand or that has spools on order as one item, grouped by
the filament line of its catalog link, then the products not in the catalog."""

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.auth import Principal
from filament_tracker.db.models import Product
from filament_tracker.db.shopping_models import HandReason
from filament_tracker.db.shopping_models import ShoppingListItem as ItemRow
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import queries
from filament_tracker.services.catalog_links import IndexedColor, catalog_link
from filament_tracker.services.shopping_list.needs import RequestNeedsReader, RequestShort
from filament_tracker.services.shopping_list.net_weight import NetWeight, net_weight
from filament_tracker.services.shopping_list.shopping_history import (
    ShoppingHistoryEntry,
    by,
    recent,
)


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


Reason = LowStock | RequestShort | HandAdded


@dataclass(frozen=True)
class ShoppingListItem:
    product: Product
    # The catalog color the product is linked to; None when it is not in the catalog.
    color: IndexedColor | None
    # Low stock first, then the requests short of it, then the hand-added reasons, oldest
    # first.
    reasons: list[Reason]
    # Its most recent shopping list history, newest first.
    shopping_history: list[ShoppingHistoryEntry] = field(default_factory=list)
    # Spools ordered and not yet arrived.
    on_order: int = 0
    # The size the requests' grams are turned into spools with.
    size: NetWeight = field(kw_only=True)

    @property
    def request_spools(self) -> int:
        """The requests' grams added up, then rounded up to spools once."""
        grams = sum(r.short_g for r in self.reasons if isinstance(r, RequestShort))
        return math.ceil(grams / self.size.grams)

    # The need it was dismissed at, if it is dismissed.
    dismissed_need: int | None = None

    @property
    def need(self) -> int:
        spools = sum(r.spools for r in self.reasons if not isinstance(r, RequestShort))
        return spools + self.request_spools

    @property
    def to_buy(self) -> int:
        return max(self.need - self.on_order, 0)

    @property
    def hidden(self) -> bool:
        """Dismissed, and no more of it needed than when it was."""
        return self.dismissed_need is not None and self.need <= self.dismissed_need

    @property
    def new_since_dismissal(self) -> int | None:
        """How many spools more it needs than when it was dismissed, once that is more."""
        if self.dismissed_need is None or self.hidden:
            return None
        return self.need - self.dismissed_need


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
    # Dismissed items still hidden, by name.
    dismissed: list[ShoppingListItem] = field(default_factory=list)

    def find(self, product_id: int) -> ShoppingListItem | None:
        """The product's item, shown or dismissed; None when it is not on the list."""
        shown = [item for line in self.lines for item in line.items] + self.not_in_catalog
        for item in shown + self.dismissed:
            if item.product.id == product_id:
                return item
        return None


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
        found[reason.product_id].append(
            HandAdded(reason.id, reason.spools, by(reason.user), reason.at)
        )
    return found


def _dismissed(session: Session) -> dict[int, ItemRow]:
    """Each dismissed product's item row."""
    query = select(ItemRow).where(ItemRow.dismissed_need.is_not(None))
    return {row.product_id: row for row in session.scalars(query)}


def _on_order(session: Session) -> dict[int, int]:
    """Each product's on order, where it is above 0."""
    rows = session.execute(select(ItemRow.product_id, ItemRow.on_order).where(ItemRow.on_order > 0))
    return {product_id: spools for product_id, spools in rows}


def read(
    session: Session, viewer: Principal | None = None, needs: RequestNeedsReader | None = None
) -> ShoppingList:
    """The shopping list as it stands now, for the viewing user. Items are by product name,
    as on Inventory. Request reasons come from `needs`, asked for `viewer`; with either left
    out there are none. A dismissal whose product needs nothing any more is cleared, so the
    caller commits."""
    by_line: dict[str, list[ShoppingListItem]] = defaultdict(list)
    listed = ShoppingList()
    hand = _hand_added(session)
    short = needs(session, viewer) if needs is not None and viewer is not None else {}
    entries = recent(session)
    dismissals = _dismissed(session)
    on_order = _on_order(session)
    for counts in queries.inventory(session):
        product = counts.product
        low = _low_stock(counts)
        reasons: list[Reason] = [low] if low else []
        reasons += short.get(product.id, [])
        reasons += hand.get(product.id, [])
        ordered = on_order.get(product.id, 0)
        if not reasons and not ordered:
            continue
        color = _color(product)
        item = ShoppingListItem(
            product,
            color,
            reasons,
            entries.get(product.id, []),
            ordered,
            size=net_weight(session, product, color),
        )
        # A product needing nothing, though still on order, keeps no dismissal.
        if item.need > 0 and product.id in dismissals:
            item = replace(item, dismissed_need=dismissals.pop(product.id).dismissed_need)
        if item.hidden:
            listed.dismissed.append(item)
        elif item.color is None:
            listed.not_in_catalog.append(item)
        else:
            by_line[item.color.line].append(item)
    # The products left need nothing: their dismissals are forgotten.
    for row in dismissals.values():
        row.dismissed_need = None
    for name in sorted(by_line, key=str.lower):
        listed.lines.append(Line(name, by_line[name]))
    return listed
