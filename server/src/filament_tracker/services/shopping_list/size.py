"""Choosing the size an item turns print requests' grams into spools with. It goes into the
shopping list history."""

from datetime import datetime

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import shopping_history
from filament_tracker.services.shopping_list.on_order import item_for


def set_size(
    session: Session, product: Product, size_g: int, user_id: int | None, now: datetime
) -> None:
    item_for(session, product.id).chosen_size_g = size_g
    session.flush()
    shopping_history.record(
        session, product.id, ShoppingAction.SIZE_CHANGED, user_id, now, size_g=size_g
    )
