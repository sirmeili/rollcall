"""A product's one shopping list item row, which holds what is stored about its item: its on
order, its chosen size and its dismissal. Its need is never stored (ADR-0021)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.shopping_models import ShoppingListItemRow


def find_item(session: Session, product_id: int) -> ShoppingListItemRow | None:
    return session.scalar(
        select(ShoppingListItemRow).where(ShoppingListItemRow.product_id == product_id)
    )


def item_for(session: Session, product_id: int) -> ShoppingListItemRow:
    """The product's one item row, made if it has none."""
    item = find_item(session, product_id)
    if item is None:
        item = ShoppingListItemRow(product_id=product_id, on_order=0)
        session.add(item)
    return item
