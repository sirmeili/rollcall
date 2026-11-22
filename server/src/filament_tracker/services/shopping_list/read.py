"""Reading the shopping list: each product that is low on stock, that print requests are
short of, or that has spools added by hand as one item, grouped by the filament line of its
catalog link, then the products not in the catalog."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.auth import Principal
from filament_tracker.db.models import Product
from filament_tracker.db.shopping_models import HandReason
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import queries
from filament_tracker.services.catalog_links import IndexedColor, catalog_link
from filament_tracker.services.shopping_list.history import HistoryEntry, recent
from filament_tracker.services.shopping_list.needs import RequestNeedsReader, RequestShort
from filament_tracker.services.shopping_list.net_weight import NetWeight, net_weight


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
    history: list[HistoryEntry] = field(default_factory=list)
    # The size the requests' grams are turned into spools with.
    size: NetWeight = field(kw_only=True)

    @property
    def request_spools(self) -> int:
        """The requests' grams added up, then rounded up to spools once."""
        grams = sum(r.short_g for r in self.reasons if isinstance(r, RequestShort))
        return math.ceil(grams / self.size.grams)

    @property
    def to_buy(self) -> int:
        spools = sum(r.spools for r in self.reasons if not isinstance(r, RequestShort))
        return spools + self.request_spools


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


def read(
    session: Session, viewer: Principal | None = None, needs: RequestNeedsReader | None = None
) -> ShoppingList:
    """The shopping list as it stands now, for the viewing user. Items are by product name,
    as on Inventory. Request reasons come from `needs`, asked for `viewer`; with either left
    out there are none."""
    by_line: dict[str, list[ShoppingListItem]] = defaultdict(list)
    listed = ShoppingList()
    hand = _hand_added(session)
    short = needs(session, viewer) if needs is not None and viewer is not None else {}
    entries = recent(session)
    for counts in queries.inventory(session):
        product = counts.product
        low = _low_stock(counts)
        reasons: list[Reason] = [low] if low else []
        reasons += short.get(product.id, [])
        reasons += hand.get(product.id, [])
        if not reasons:
            continue
        color = _color(product)
        item = ShoppingListItem(
            product,
            color,
            reasons,
            entries.get(product.id, []),
            size=net_weight(session, product, color),
        )
        if item.color is None:
            listed.not_in_catalog.append(item)
        else:
            by_line[item.color.line].append(item)
    for name in sorted(by_line, key=str.lower):
        listed.lines.append(Line(name, by_line[name]))
    return listed
