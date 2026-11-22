"""Reading the shopping list: each low-stock product as one item, grouped by the filament
line of its catalog link, then the products not in the catalog."""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import queries
from filament_tracker.services.catalog_links import IndexedColor, catalog_link


@dataclass(frozen=True)
class LowStock:
    """The product is low: buying `spools` takes its Sealed count above its threshold."""

    spools: int
    sealed: int
    threshold: int


@dataclass(frozen=True)
class ShoppingListItem:
    product: Product
    # The catalog color the product is linked to; None when it is not in the catalog.
    color: IndexedColor | None
    reasons: list[LowStock]

    @property
    def to_buy(self) -> int:
        return sum(reason.spools for reason in self.reasons)


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


def read(session: Session) -> ShoppingList:
    """The shopping list as it stands now. Items are by product name, as on Inventory."""
    by_line: dict[str, list[ShoppingListItem]] = defaultdict(list)
    listed = ShoppingList()
    for counts in queries.inventory(session):
        low = _low_stock(counts)
        if low is None:
            continue
        item = ShoppingListItem(counts.product, _color(counts.product), [low])
        if item.color is None:
            listed.not_in_catalog.append(item)
        else:
            by_line[item.color.line].append(item)
    for name in sorted(by_line, key=str.lower):
        listed.lines.append(Line(name, by_line[name]))
    return listed
