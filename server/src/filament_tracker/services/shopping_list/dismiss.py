"""Dismiss sets a shopping list item aside until more of it is needed: it stores the need at
that moment and removes the item's hand-added reasons. Bring back clears the dismissal. Both
go into the shopping list history."""

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from filament_tracker.db.shopping_models import HandReason
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import shopping_history
from filament_tracker.services.shopping_list.on_order import find_item, item_for
from filament_tracker.services.shopping_list.read import ShoppingListItem


class NotDismissed(LookupError):
    """The product's item is not dismissed."""


def dismiss(session: Session, item: ShoppingListItem, user_id: int | None, now: datetime) -> None:
    """Hide the item while its need stays at or below what it is now."""
    product_id = item.product.id
    item_for(session, product_id).dismissed_need = item.need
    session.execute(delete(HandReason).where(HandReason.product_id == product_id))
    shopping_history.record(
        session, product_id, ShoppingAction.DISMISSED, user_id, now, spools=item.need
    )


def bring_back(session: Session, product_id: int, user_id: int | None, now: datetime) -> None:
    """Clear the product's dismissal, so its item shows again whatever its need."""
    row = find_item(session, product_id)
    if row is None or row.dismissed_need is None:
        raise NotDismissed(product_id)
    row.dismissed_need = None
    shopping_history.record(session, product_id, ShoppingAction.BROUGHT_BACK, user_id, now)
