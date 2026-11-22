"""Dismiss sets a shopping list item aside until more of it is needed: it stores the need at
that moment and removes the item's hand-added reasons. Bring back clears the dismissal. Both
go into the shopping list history."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from filament_tracker.db.shopping_models import HandReason
from filament_tracker.db.shopping_models import ShoppingListItem as ItemRow
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import history
from filament_tracker.services.shopping_list.read import ShoppingListItem


class NotDismissed(LookupError):
    """The product's item is not dismissed."""


def _row(session: Session, product_id: int) -> ItemRow | None:
    return session.scalar(select(ItemRow).where(ItemRow.product_id == product_id))


def dismiss(session: Session, item: ShoppingListItem, user_id: int | None, now: datetime) -> None:
    """Hide the item while its need stays at or below what it is now."""
    product_id = item.product.id
    row = _row(session, product_id)
    if row is None:
        row = ItemRow(product_id=product_id)
        session.add(row)
    row.dismissed_need = item.need
    session.execute(delete(HandReason).where(HandReason.product_id == product_id))
    history.record(session, product_id, ShoppingAction.DISMISSED, user_id, now, spools=item.need)


def bring_back(session: Session, product_id: int, user_id: int | None, now: datetime) -> None:
    """Clear the product's dismissal, so its item shows again whatever its need."""
    row = _row(session, product_id)
    if row is None or row.dismissed_need is None:
        raise NotDismissed(product_id)
    row.dismissed_need = None
    history.record(session, product_id, ShoppingAction.BROUGHT_BACK, user_id, now)
