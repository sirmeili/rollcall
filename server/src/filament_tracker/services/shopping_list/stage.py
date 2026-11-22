"""How far along buying a product is: its shopping list item's stage, which a print request's
short choice shows. The stage belongs to the product, so every request short of one product
shows the same one."""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.services.shopping_list.needs import RequestNeedsReader
from filament_tracker.services.shopping_list.read import ShoppingListItem, read


class Stage(StrEnum):
    # Spools to buy, none on order.
    ON_LIST = "on_list"
    # Some on order, more to buy.
    PARTLY_ORDERED = "partly_ordered"
    # Nothing left to buy.
    ORDERED = "ordered"


@dataclass(frozen=True)
class ItemStage:
    product_id: int
    stage: Stage
    on_order: int
    need: int


def _stage(item: ShoppingListItem) -> ItemStage:
    if item.to_buy == 0:
        stage = Stage.ORDERED
    elif item.on_order == 0:
        stage = Stage.ON_LIST
    else:
        stage = Stage.PARTLY_ORDERED
    return ItemStage(item.product.id, stage, item.on_order, item.need)


def stages(
    session: Session, viewer: Principal, needs: RequestNeedsReader, product_ids: set[int]
) -> dict[int, ItemStage]:
    """The stage of each of these products' items, by product ID, read with the request-needs
    reader so the print requests count. A product with no item, or whose item is dismissed
    and still hidden, has none."""
    if not product_ids:
        return {}
    listed = read(session, viewer, needs)
    found = {}
    for product_id in product_ids:
        item = listed.find(product_id)
        if item is not None and not item.hidden:
            found[product_id] = _stage(item)
    return found
