"""Spools an Editor or Admin puts on the list by hand: each is a hand-added reason on the
product's one item. Adding and removing one go into the shopping list history."""

from datetime import datetime

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.db.shopping_models import HandReason
from filament_tracker.domain.enums import ShoppingAction
from filament_tracker.services.shopping_list import history


class NoSuchReason(LookupError):
    """No hand-added reason has this ID."""


def add_by_hand(
    session: Session, product: Product, spools: int, user_id: int | None, now: datetime
) -> HandReason:
    """Add spools to the product's item, as a reason of their own. A product already on the
    list gets another reason, never a second item."""
    reason = HandReason(product_id=product.id, spools=spools, user_id=user_id, at=now)
    session.add(reason)
    history.record(session, product.id, ShoppingAction.ADDED_BY_HAND, user_id, now, spools=spools)
    return reason


def remove_hand_reason(
    session: Session, reason_id: int, user_id: int | None, now: datetime
) -> None:
    reason = session.get(HandReason, reason_id)
    if reason is None:
        raise NoSuchReason(reason_id)
    session.delete(reason)
    history.record(
        session,
        reason.product_id,
        ShoppingAction.REMOVED_BY_HAND,
        user_id,
        now,
        spools=reason.spools,
    )
