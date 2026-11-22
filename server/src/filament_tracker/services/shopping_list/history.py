"""The shopping list history: what people did to each product's item, with who and when and
the item's on order once it was done. Entries are only ever added, never edited."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.db.shopping_models import ShoppingHistory, ShoppingListItem
from filament_tracker.domain.enums import ShoppingAction

# How many entries an item's expanded view shows.
RECENT = 5


@dataclass(frozen=True)
class HistoryEntry:
    action: ShoppingAction
    # The spools or the size in grams the action concerned, if any.
    spools: int | None
    size_g: int | None
    # The item's on order once it was done.
    on_order: int
    # Who did it: None for a token, which acts for no user.
    by: str | None
    at: datetime


def on_order(session: Session, product_id: int) -> int:
    item = session.scalar(select(ShoppingListItem).where(ShoppingListItem.product_id == product_id))
    return item.on_order if item else 0


def record(
    session: Session,
    product_id: int,
    action: ShoppingAction,
    user_id: int | None,
    now: datetime,
    *,
    spools: int | None = None,
    size_g: int | None = None,
) -> None:
    session.add(
        ShoppingHistory(
            product_id=product_id,
            action=action,
            spools=spools,
            size_g=size_g,
            on_order=on_order(session, product_id),
            user_id=user_id,
            at=now,
        )
    )
    session.flush()


def recent(session: Session) -> dict[int, list[HistoryEntry]]:
    """Each product's most recent entries, newest first."""
    found: dict[int, list[HistoryEntry]] = defaultdict(list)
    query = (
        select(ShoppingHistory)
        .options(selectinload(ShoppingHistory.user))
        .order_by(ShoppingHistory.at.desc(), ShoppingHistory.id.desc())
    )
    for entry in session.scalars(query):
        kept = found[entry.product_id]
        if len(kept) < RECENT:
            by = entry.user.username if entry.user else None
            kept.append(
                HistoryEntry(entry.action, entry.spools, entry.size_g, entry.on_order, by, entry.at)
            )
    return found
