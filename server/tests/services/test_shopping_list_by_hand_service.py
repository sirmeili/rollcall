"""Inventory's shopping list service, called directly: adding to the list by hand, the product
for a catalog color, and the shopping list history those actions start."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from test_shopping_list_service import catalog_line, items, product

from filament_tracker.db.models import Product, User
from filament_tracker.domain.enums import Role, ShoppingAction
from filament_tracker.services import shopping_list
from filament_tracker.services.accounts import create_user
from filament_tracker.services.catalog_links import UnknownColor, catalog_link, set_manual
from filament_tracker.services.shopping_list import (
    HandAdded,
    LowStock,
    NoSuchReason,
    ShoppingHistoryEntry,
    add_by_hand,
    product_for_color,
    remove_hand_reason,
)

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def frank(session: Session) -> User:
    return create_user(session, "frank", "a long enough password", Role.EDITOR)


def test_a_catalog_color_with_no_product_gets_a_from_the_catalog_one(
    session: Session, frank: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})

    made = product_for_color(session, "jade", frank.id, NOW)

    assert made.display_name == "jade PLA Basic"
    assert made.filament_type == "PLA"
    assert made.color_rgba == "102030FF"
    assert made.provisional and made.from_catalog
    assert (made.material_id, made.variant_id) == (None, None)
    link = catalog_link(made)
    assert link is not None and link.color is not None
    assert (link.color.uuid, link.how, link.linked_by, link.linked_at) == (
        "jade",
        "hand",
        "frank",
        NOW,
    )


def test_a_catalog_color_already_linked_reuses_its_product(session: Session, frank: User) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    jade = product(session, "Jade White", threshold=0)
    set_manual(session, jade, "jade", None, NOW)

    found = product_for_color(session, "jade", frank.id, NOW)

    assert found.id == jade.id
    assert not found.from_catalog
    assert session.query(Product).count() == 1


def test_a_color_not_in_the_catalog_is_refused(session: Session, frank: User) -> None:
    with pytest.raises(UnknownColor):
        product_for_color(session, "nowhere", frank.id, NOW)
    assert session.query(Product).count() == 0


def test_spools_added_by_hand_put_a_product_on_the_list(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=0)

    add_by_hand(session, black, 3, frank.id, NOW)

    [item] = shopping_list.read(session).not_in_catalog
    assert item.product.id == black.id
    assert item.to_buy == 3
    [reason] = item.reasons
    assert isinstance(reason, HandAdded)
    assert (reason.spools, reason.by, reason.at) == (3, "frank", NOW)


def test_adding_to_a_product_already_on_the_list_adds_a_reason_to_its_one_item(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=2, sealed=1)

    add_by_hand(session, black, 1, frank.id, NOW)
    add_by_hand(session, black, 2, None, NOW)

    [item] = shopping_list.read(session).not_in_catalog
    assert item.to_buy == 2 + 1 + 2
    assert [type(r) for r in item.reasons] == [LowStock, HandAdded, HandAdded]
    assert [r.by for r in item.reasons if isinstance(r, HandAdded)] == ["frank", None]


def test_a_from_the_catalog_product_added_by_hand_is_listed_in_its_line(
    session: Session, frank: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})

    add_by_hand(session, product_for_color(session, "jade", frank.id, NOW), 2, frank.id, NOW)

    [line] = shopping_list.read(session).lines
    assert (line.name, line.to_buy) == ("PLA Basic", 2)
    assert items(session) == {"jade PLA Basic": 2}


def test_a_hand_added_reason_can_be_removed(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=1)
    first = add_by_hand(session, black, 2, frank.id, NOW)
    add_by_hand(session, black, 3, frank.id, NOW)

    remove_hand_reason(session, first.id, frank.id, NOW)

    assert items(session) == {"Black": 2 + 3}


def test_a_product_leaves_the_list_once_its_only_hand_reason_is_removed(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=0)
    reason = add_by_hand(session, black, 2, frank.id, NOW)

    remove_hand_reason(session, reason.id, frank.id, NOW)

    assert items(session) == {}


def test_removing_a_reason_that_is_not_there_is_refused(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=0)
    reason = add_by_hand(session, black, 2, frank.id, NOW)
    remove_hand_reason(session, reason.id, frank.id, NOW)

    with pytest.raises(NoSuchReason):
        remove_hand_reason(session, reason.id, frank.id, NOW)


def test_adding_and_removing_by_hand_go_into_the_items_history_newest_first(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=0)
    later = NOW + timedelta(hours=1)
    first = add_by_hand(session, black, 2, frank.id, NOW)
    add_by_hand(session, black, 1, None, NOW + timedelta(minutes=30))
    remove_hand_reason(session, first.id, frank.id, later)

    [item] = shopping_list.read(session).not_in_catalog

    assert item.shopping_history == [
        ShoppingHistoryEntry(ShoppingAction.REMOVED_BY_HAND, 2, None, 0, "frank", later),
        ShoppingHistoryEntry(
            ShoppingAction.ADDED_BY_HAND, 1, None, 0, None, NOW + timedelta(minutes=30)
        ),
        ShoppingHistoryEntry(ShoppingAction.ADDED_BY_HAND, 2, None, 0, "frank", NOW),
    ]


def test_an_item_shows_only_its_recent_history(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=0)
    for minutes in range(7):
        add_by_hand(session, black, 1, frank.id, NOW + timedelta(minutes=minutes))

    [item] = shopping_list.read(session).not_in_catalog

    assert [entry.at for entry in item.shopping_history] == [
        NOW + timedelta(minutes=m) for m in (6, 5, 4, 3, 2)
    ]
