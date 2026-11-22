"""Inventory's shopping list service, called directly: on order up on Ordered and set by hand,
down on each spool's first appearance in stock and back on an undo, and to buy from it."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from test_ams import printer, trays  # noqa: F401 - the printer fixture
from test_ams import product as ams_product
from test_shopping_list_service import product

from filament_tracker.db.models import Printer, Product, Spool
from filament_tracker.domain.enums import EventSource, EventType, ShoppingAction
from filament_tracker.services import shopping_list
from filament_tracker.services.ams import ingest
from filament_tracker.services.edits import add_placeholder, record_action
from filament_tracker.services.events import append_event, revert_event
from filament_tracker.services.shopping_list import (
    ShoppingListItem,
    add_by_hand,
    ordered,
    set_on_order,
)

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


def listed(session: Session) -> dict[str, ShoppingListItem]:
    found = shopping_list.read(session)
    return {
        i.product.display_name: i
        for i in [*found.not_in_catalog] + [i for line in found.lines for i in line.items]
    }


def on_order(session: Session, item: Product) -> int:
    found = listed(session).get(item.display_name)
    return found.on_order if found else 0


def test_ordered_adds_to_on_order_and_takes_it_off_to_buy(session: Session) -> None:
    black = product(session, "Black", threshold=0)
    add_by_hand(session, black, 3, None, NOW)

    ordered(session, black, 1, None, NOW)
    ordered(session, black, 1, None, NOW)

    item = listed(session)["Black"]
    assert (item.need, item.on_order, item.to_buy) == (3, 2, 1)


def test_setting_on_order_replaces_it(session: Session) -> None:
    black = product(session, "Black", threshold=0)
    add_by_hand(session, black, 3, None, NOW)
    ordered(session, black, 2, None, NOW)

    set_on_order(session, black, 1, None, NOW)

    assert listed(session)["Black"].on_order == 1


def test_to_buy_never_goes_below_0(session: Session) -> None:
    black = product(session, "Black", threshold=0)
    add_by_hand(session, black, 1, None, NOW)

    ordered(session, black, 3, None, NOW)

    item = listed(session)["Black"]
    assert (item.need, item.on_order, item.to_buy) == (1, 3, 0)


def test_a_product_with_only_on_order_stays_on_the_list(session: Session) -> None:
    black = product(session, "Black", threshold=0)

    ordered(session, black, 2, None, NOW)

    item = listed(session)["Black"]
    assert (item.need, item.on_order, item.to_buy) == (0, 2, 0)


def test_a_product_with_no_need_and_nothing_on_order_leaves_the_list(session: Session) -> None:
    black = product(session, "Black", threshold=0)
    ordered(session, black, 2, None, NOW)

    set_on_order(session, black, 0, None, NOW)

    assert listed(session) == {}


def test_ordered_and_set_on_order_go_into_the_history_with_the_resulting_on_order(
    session: Session,
) -> None:
    black = product(session, "Black", threshold=0)

    ordered(session, black, 2, None, NOW)
    ordered(session, black, 1, None, NOW)
    set_on_order(session, black, 1, None, LATER)

    history = listed(session)["Black"].history
    assert [(e.action, e.spools, e.on_order) for e in history] == [
        (ShoppingAction.ON_ORDER_CHANGED, None, 1),
        (ShoppingAction.ORDERED, 1, 3),
        (ShoppingAction.ORDERED, 2, 2),
    ]


def test_on_order_never_goes_below_0(session: Session) -> None:
    black = product(session, "Black", threshold=0)

    with pytest.raises(ValueError):
        set_on_order(session, black, -1, None, NOW)
    with pytest.raises(ValueError):
        ordered(session, black, 0, None, NOW)
    assert on_order(session, black) == 0


# --- Arrivals ------------------------------------------------------------------------------


def _ordered_black(session: Session, spools: int = 2) -> Product:
    black = product(session, "Black", threshold=0)
    ordered(session, black, spools, None, NOW)
    return black


def _new_spool(session: Session, item: Product) -> Spool:
    spool = Spool(product=item, tray_uid="AB" * 16)
    session.add(spool)
    session.flush()
    return spool


def test_a_spool_received_in_the_web_app_takes_one_off(session: Session) -> None:
    black = _ordered_black(session)

    record_action(session, _new_spool(session, black), EventType.RECEIVED, NOW, user_id=None)

    assert on_order(session, black) == 1


def test_a_spool_received_from_a_scan_takes_one_off(session: Session) -> None:
    black = _ordered_black(session)

    append_event(session, _new_spool(session, black), EventType.RECEIVED, EventSource.SCANNER, NOW)

    assert on_order(session, black) == 1


def test_a_spool_first_scanned_as_opened_takes_one_off(session: Session) -> None:
    black = _ordered_black(session)

    append_event(session, _new_spool(session, black), EventType.OPENED, EventSource.SCANNER, NOW)

    assert on_order(session, black) == 1


def test_a_placeholder_added_by_hand_takes_one_off(session: Session) -> None:
    black = _ordered_black(session)

    add_placeholder(session, black, NOW, user_id=None)
    add_placeholder(session, black, NOW, user_id=None)

    assert on_order(session, black) == 0


def test_a_spool_first_seen_by_the_ams_takes_one_off(
    session: Session,
    printer: Printer,  # noqa: F811 - the fixture
) -> None:
    black = ams_product(session)
    ordered(session, black, 2, None, NOW)

    ingest(session, printer, trays("pushall"), NOW)

    assert on_order(session, black) == 1


def test_each_spool_counts_once(session: Session) -> None:
    black = _ordered_black(session)
    spool = _new_spool(session, black)

    append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, NOW)
    append_event(session, spool, EventType.OPENED, EventSource.SCANNER, LATER)
    append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, LATER)

    assert on_order(session, black) == 1


def test_a_scan_linked_to_a_placeholder_does_not_count_it_again(session: Session) -> None:
    black = _ordered_black(session)
    placeholder = add_placeholder(session, black, NOW, user_id=None)

    append_event(session, placeholder, EventType.RECEIVED, EventSource.SCANNER, LATER, flag=True)

    assert on_order(session, black) == 1


def test_an_arrival_never_takes_on_order_below_0(session: Session) -> None:
    black = product(session, "Black", threshold=0)
    ordered(session, black, 1, None, NOW)
    add_placeholder(session, black, NOW, user_id=None)

    add_placeholder(session, black, NOW, user_id=None)

    assert on_order(session, black) == 0


def test_undoing_the_received_that_counted_a_spool_gives_the_one_back(session: Session) -> None:
    black = _ordered_black(session)
    spool = _new_spool(session, black)
    received = append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, NOW).event

    revert_event(session, received, EventSource.UI, LATER)

    assert on_order(session, black) == 2


def test_a_spool_received_again_after_an_undo_counts_again(session: Session) -> None:
    black = _ordered_black(session)
    spool = _new_spool(session, black)
    received = append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, NOW).event
    revert_event(session, received, EventSource.UI, LATER)

    append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, LATER)

    assert on_order(session, black) == 1


def test_undoing_an_event_that_did_not_count_the_spool_gives_nothing_back(
    session: Session,
) -> None:
    black = _ordered_black(session)
    spool = _new_spool(session, black)
    append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, NOW)
    opened = append_event(session, spool, EventType.OPENED, EventSource.SCANNER, LATER).event

    revert_event(session, opened, EventSource.UI, LATER)

    assert on_order(session, black) == 1


def test_undoing_the_received_of_a_spool_that_arrived_before_the_shopping_list_gives_nothing(
    session: Session,
) -> None:
    black = product(session, "Black", threshold=0)
    spool = _new_spool(session, black)
    received = append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, NOW).event
    # As the migration leaves every spool already here: counted, by no event.
    spool.arrival_counted, spool.arrival_event_id = True, None
    ordered(session, black, 2, None, NOW)

    revert_event(session, received, EventSource.UI, LATER)
    append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, LATER)

    assert on_order(session, black) == 2


def test_undoing_a_received_that_took_nothing_off_gives_nothing_back(session: Session) -> None:
    black = product(session, "Black", threshold=0)
    spool = _new_spool(session, black)
    received = append_event(session, spool, EventType.RECEIVED, EventSource.SCANNER, NOW).event
    ordered(session, black, 2, None, NOW)

    revert_event(session, received, EventSource.UI, LATER)

    assert on_order(session, black) == 2
