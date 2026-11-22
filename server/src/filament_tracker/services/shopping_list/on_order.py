"""On order: spools of a product bought and on their way. Ordered adds to it, an Editor or
Admin can set it to any number, and each spool's first appearance in stock takes one off
(arrivals). It belongs to the product's item, never to a reason."""

from datetime import datetime

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import shopping_history
from filament_tracker.services.shopping_list.items import item_for


def ordered(
    session: Session, product: Product, spools: int, user_id: int | None, now: datetime
) -> None:
    """Add spools to the product's on order."""
    if spools < 1:
        raise ValueError("order at least one spool")
    item_for(session, product.id).on_order += spools
    shopping_history.record(
        session, product.id, ShoppingAction.ORDERED, user_id, now, spools=spools
    )


def set_on_order(
    session: Session, product: Product, spools: int, user_id: int | None, now: datetime
) -> None:
    """Replace the product's on order, to fix a typo or a cancelled order."""
    if spools < 0:
        raise ValueError("on order cannot go below 0")
    item_for(session, product.id).on_order = spools
    shopping_history.record(session, product.id, ShoppingAction.ON_ORDER_CHANGED, user_id, now)
