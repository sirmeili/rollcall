"""Choosing the size an item turns print requests' grams into spools with. It goes into the
shopping list history."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.db.shopping_models import ShoppingListItem
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import history


def set_size(
    session: Session, product: Product, size_g: int, user_id: int | None, now: datetime
) -> None:
    item = session.scalar(select(ShoppingListItem).where(ShoppingListItem.product_id == product.id))
    if item is None:
        item = ShoppingListItem(product_id=product.id)
        session.add(item)
    item.chosen_size_g = size_g
    session.flush()
    history.record(session, product.id, ShoppingAction.SIZE_CHANGED, user_id, now, size_g=size_g)
