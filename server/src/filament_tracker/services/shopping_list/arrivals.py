"""Arrivals: each spool takes one off its product's on order the first time it appears in
stock, whichever way it came (a Received from a scan or the web app, a placeholder added by
hand, a spool first seen by the AMS). The event log calls these on every append and undo.
Arrivals are not shopping list history."""

from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Spool
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services.shopping_list.on_order import find_item, item_for

IN_STOCK = {SpoolState.SEALED, SpoolState.OPEN}


def appended(session: Session, spool: Spool, event: Event, before: SpoolState | None) -> None:
    """The event was appended to a spool that was in `before` state. If it brought a spool
    never counted from no state into stock, count it, and take one off on order if any."""
    if spool.arrival_counted or before is not None or spool.state not in IN_STOCK:
        return
    spool.arrival_counted = True
    item = find_item(session, spool.product_id)
    if item is not None and item.on_order > 0:
        item.on_order -= 1
        spool.arrival_event_id = event.id


def undone(session: Session, spool: Spool, target: Event) -> None:
    """The target event was undone. If it is the one that took the spool off on order, give
    the one back; the spool counts again when it next appears in stock."""
    if spool.arrival_event_id != target.id:
        return
    item_for(session, spool.product_id).on_order += 1
    spool.arrival_counted = False
    spool.arrival_event_id = None
