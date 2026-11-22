"""On order: spools of a product bought and on their way. Ordered adds to it, an Editor or
Admin can set it to any number, and each spool's first appearance in stock takes one off
(arrivals). It belongs to the product's item, never to a reason."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.db.shopping_models import ShoppingListItem
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import history


def find_item(session: Session, product_id: int) -> ShoppingListItem | None:
    return session.scalar(select(ShoppingListItem).where(ShoppingListItem.product_id == product_id))


def item_for(session: Session, product_id: int) -> ShoppingListItem:
    """The product's one item row, made if it has none."""
    item = find_item(session, product_id)
    if item is None:
        item = ShoppingListItem(product_id=product_id, on_order=0)
        session.add(item)
    return item


def ordered(
    session: Session, product: Product, spools: int, user_id: int | None, now: datetime
) -> None:
    """Add spools to the product's on order."""
    if spools < 1:
        raise ValueError("order at least one spool")
    item_for(session, product.id).on_order += spools
    history.record(session, product.id, ShoppingAction.ORDERED, user_id, now, spools=spools)


def set_on_order(
    session: Session, product: Product, spools: int, user_id: int | None, now: datetime
) -> None:
    """Replace the product's on order, to fix a typo or a cancelled order."""
    if spools < 0:
        raise ValueError("on order cannot go below 0")
    item_for(session, product.id).on_order = spools
    history.record(session, product.id, ShoppingAction.ON_ORDER_CHANGED, user_id, now)
