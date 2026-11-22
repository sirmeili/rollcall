"""Inventory's shopping list service, called directly: Dismiss setting an item aside until more
of it is needed, and Bring back."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session
from test_shopping_list_service import items, product

from filament_tracker.db.models import Product, Spool, User
from filament_tracker.domain.enums import Role, ShoppingAction, SpoolState
from filament_tracker.services import shopping_list
from filament_tracker.services.accounts import create_user
from filament_tracker.services.shopping_list import (
    LowStock,
    NotDismissed,
    add_by_hand,
    bring_back,
    dismiss,
    ordered,
)

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def frank(session: Session) -> User:
    return create_user(session, "frank", "a long enough password", Role.EDITOR)


def dismiss_now(session: Session, product: Product, user: User) -> None:
    item = shopping_list.read(session).find(product.id)
    assert item is not None
    dismiss(session, item, user.id, NOW)


def use_one(session: Session, product: Product) -> None:
    """Open one of the product's Sealed spools, so it needs one spool more."""
    spool = next(s for s in product.spools if s.state is SpoolState.SEALED)
    spool.state = SpoolState.OPEN
    session.flush()


def test_a_dismissed_item_is_hidden_from_the_list(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)

    dismiss_now(session, black, frank)

    assert items(session) == {}


def test_a_dismissed_item_is_listed_under_dismissed(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)

    dismiss_now(session, black, frank)

    [item] = shopping_list.read(session).dismissed
    assert item.product.id == black.id
    assert item.dismissed_need == 2
    assert item.reasons == [LowStock(spools=2, sealed=1, threshold=2)]


def test_a_dismissed_item_stays_hidden_while_its_need_is_no_higher(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=3, sealed=1)
    dismiss_now(session, black, frank)
    session.add(Spool(product=black, state=SpoolState.SEALED))
    session.flush()

    assert items(session) == {}
    [item] = shopping_list.read(session).dismissed
    assert (item.need, item.dismissed_need) == (2, 3)


def test_a_dismissed_item_comes_back_once_its_need_is_higher_showing_whats_new(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=2, sealed=2)
    dismiss_now(session, black, frank)

    use_one(session, black)

    assert items(session) == {"Black": 2}
    item = shopping_list.read(session).find(black.id)
    assert item is not None
    assert item.new_since_dismissal == 1
    assert shopping_list.read(session).dismissed == []


def test_an_item_never_dismissed_has_nothing_new(session: Session) -> None:
    black = product(session, "Black", threshold=2, sealed=1)

    item = shopping_list.read(session).find(black.id)

    assert item is not None
    assert item.new_since_dismissal is None


def test_a_dismissal_is_cleared_once_the_need_reaches_0(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)
    dismiss_now(session, black, frank)
    for _ in range(2):
        session.add(Spool(product=black, state=SpoolState.SEALED))
    session.flush()
    assert items(session) == {}

    # Low again, by less than when it was dismissed: the need starts fresh.
    for _ in range(2):
        use_one(session, black)

    assert items(session) == {"Black": 2}
    item = shopping_list.read(session).find(black.id)
    assert item is not None
    assert item.dismissed_need is None


def test_dismiss_removes_hand_added_reasons(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)
    add_by_hand(session, black, 3, frank.id, NOW)

    dismiss_now(session, black, frank)

    [item] = shopping_list.read(session).dismissed
    assert item.reasons == [LowStock(spools=2, sealed=1, threshold=2)]
    # The need it was dismissed at counts the hand-added spools.
    assert item.dismissed_need == 5


def test_dismissing_an_item_with_only_hand_added_reasons_takes_it_off_the_list(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=0)
    add_by_hand(session, black, 3, frank.id, NOW)

    dismiss_now(session, black, frank)

    listed = shopping_list.read(session)
    assert items(session) == {}
    assert listed.dismissed == []


def test_bring_back_shows_a_dismissed_item_again(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)
    dismiss_now(session, black, frank)

    bring_back(session, black.id, frank.id, NOW)

    assert items(session) == {"Black": 2}
    item = shopping_list.read(session).find(black.id)
    assert item is not None
    assert item.dismissed_need is None
    assert shopping_list.read(session).dismissed == []


def test_bring_back_on_an_item_not_dismissed_is_refused(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)

    with pytest.raises(NotDismissed):
        bring_back(session, black.id, frank.id, NOW)


def test_dismiss_and_bring_back_are_in_the_history(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)
    dismiss_now(session, black, frank)
    bring_back(session, black.id, frank.id, NOW)

    item = shopping_list.read(session).find(black.id)

    assert item is not None
    assert [(e.action, e.spools, e.by) for e in item.shopping_history] == [
        (ShoppingAction.BROUGHT_BACK, None, "frank"),
        (ShoppingAction.DISMISSED, 2, "frank"),
    ]


def test_a_dismissed_item_on_order_stays_hidden(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=2, sealed=1)
    ordered(session, black, 1, frank.id, NOW)

    dismiss_now(session, black, frank)

    assert items(session) == {}
    [item] = shopping_list.read(session).dismissed
    assert (item.on_order, item.dismissed_need) == (1, 2)


def test_an_item_needing_nothing_but_on_order_keeps_no_dismissal(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=2, sealed=1)
    ordered(session, black, 1, frank.id, NOW)
    dismiss_now(session, black, frank)
    for _ in range(2):
        session.add(Spool(product=black, state=SpoolState.SEALED))
    session.flush()

    # Still on order, so on the list, with its dismissal forgotten.
    assert items(session) == {"Black": 0}
    for _ in range(2):
        use_one(session, black)
    item = shopping_list.read(session).find(black.id)
    assert item is not None
    assert (item.dismissed_need, item.hidden) == (None, False)
