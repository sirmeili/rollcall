"""Inventory's shopping list service, called directly: Viewers' suggestions, which count toward
nothing until an Editor or Admin adds one (a hand-added reason) or dismisses it."""

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
    NoSuchSuggestion,
    ShoppingHistoryEntry,
    SuggestionDecided,
    add_suggestion,
    dismiss_suggestion,
    open_suggestions,
    suggest,
)

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


@pytest.fixture
def vic(session: Session) -> User:
    return create(session, "vic", Role.VIEWER)


@pytest.fixture
def frank(session: Session) -> User:
    return create(session, "frank", Role.EDITOR)


def create(session: Session, name: str, role: Role) -> User:
    return create_user(session, name, "a long enough password", role)


def test_a_suggested_product_waits_in_the_suggestions(session: Session, vic: User) -> None:
    black = product(session, "Black", threshold=0)

    suggest(session, black, None, 2, vic.id, NOW)

    [waiting] = open_suggestions(session)
    assert waiting.product is not None and waiting.product.id == black.id
    assert waiting.color is None
    assert (waiting.spools, waiting.by, waiting.at) == (2, "vic", NOW)


def test_a_suggestion_counts_toward_nothing(session: Session, vic: User) -> None:
    black = product(session, "Black", threshold=0)
    low = product(session, "Low", threshold=2, sealed=1)

    suggest(session, black, None, 2, vic.id, NOW)
    suggest(session, low, None, 5, vic.id, NOW)

    assert items(session) == {"Low": 2}


def test_a_suggested_catalog_color_with_no_product_makes_no_product(
    session: Session, vic: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})

    suggest(session, None, "jade", 1, vic.id, NOW)

    assert session.query(Product).count() == 0
    [waiting] = open_suggestions(session)
    assert waiting.product is None
    assert waiting.color is not None
    assert (waiting.color.uuid, waiting.color.line, waiting.color.bambu_code) == (
        "jade",
        "PLA Basic",
        "10100",
    )


def test_a_suggested_catalog_color_with_a_product_suggests_that_product(
    session: Session, vic: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    jade = product(session, "Jade White", threshold=0)
    set_manual(session, jade, "jade", None, NOW)

    suggest(session, None, "jade", 1, vic.id, NOW)

    [waiting] = open_suggestions(session)
    assert waiting.product is not None and waiting.product.id == jade.id


def test_suggesting_a_color_not_in_the_catalog_is_refused(session: Session, vic: User) -> None:
    with pytest.raises(UnknownColor):
        suggest(session, None, "nowhere", 1, vic.id, NOW)
    assert open_suggestions(session) == []


def test_suggestions_wait_oldest_first(session: Session, vic: User) -> None:
    black = product(session, "Black", threshold=0)
    white = product(session, "White", threshold=0)
    suggest(session, white, None, 1, vic.id, LATER)
    suggest(session, black, None, 1, None, NOW)

    assert [s.product.display_name for s in open_suggestions(session) if s.product] == [
        "Black",
        "White",
    ]
    assert open_suggestions(session)[0].by is None


def test_adding_a_suggestion_makes_it_a_hand_added_reason(
    session: Session, vic: User, frank: User
) -> None:
    black = product(session, "Black", threshold=0)
    suggestion = suggest(session, black, None, 2, vic.id, NOW)

    add_suggestion(session, suggestion.id, frank.id, LATER)

    assert open_suggestions(session) == []
    [item] = shopping_list.read(session).not_in_catalog
    assert item.to_buy == 2
    [reason] = item.reasons
    assert isinstance(reason, HandAdded)
    assert (reason.spools, reason.by, reason.at) == (2, "frank", LATER)


def test_adding_a_suggested_catalog_color_makes_its_from_the_catalog_product_then(
    session: Session, vic: User, frank: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    suggestion = suggest(session, None, "jade", 3, vic.id, NOW)

    add_suggestion(session, suggestion.id, frank.id, LATER)

    [made] = session.query(Product).all()
    assert made.from_catalog
    link = catalog_link(made)
    assert link is not None and link.color is not None
    assert (link.color.uuid, link.linked_by) == ("jade", "frank")
    assert items(session) == {"jade PLA Basic": 3}


def test_adding_a_suggested_color_since_linked_puts_it_on_the_linked_product(
    session: Session, vic: User, frank: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    suggestion = suggest(session, None, "jade", 1, vic.id, NOW)
    jade = product(session, "Jade White", threshold=0)
    set_manual(session, jade, "jade", None, NOW)

    add_suggestion(session, suggestion.id, frank.id, LATER)

    assert session.query(Product).count() == 1
    assert items(session) == {"Jade White": 1}


def test_a_dismissed_suggestion_leaves_the_suggestions_and_adds_nothing(
    session: Session, vic: User, frank: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    suggestion = suggest(session, None, "jade", 1, vic.id, NOW)

    dismiss_suggestion(session, suggestion.id, frank.id, LATER)

    assert open_suggestions(session) == []
    assert items(session) == {}
    assert session.query(Product).count() == 0


def test_a_decided_suggestion_cannot_be_decided_again(
    session: Session, vic: User, frank: User
) -> None:
    black = product(session, "Black", threshold=0)
    added = suggest(session, black, None, 1, vic.id, NOW)
    dismissed = suggest(session, black, None, 1, vic.id, NOW)
    add_suggestion(session, added.id, frank.id, LATER)
    dismiss_suggestion(session, dismissed.id, frank.id, LATER)

    for decided in (added, dismissed):
        with pytest.raises(SuggestionDecided):
            add_suggestion(session, decided.id, frank.id, LATER)
        with pytest.raises(SuggestionDecided):
            dismiss_suggestion(session, decided.id, frank.id, LATER)
    assert items(session) == {"Black": 1}


def test_deciding_a_suggestion_that_is_not_there_is_refused(session: Session, frank: User) -> None:
    with pytest.raises(NoSuchSuggestion):
        add_suggestion(session, 99, frank.id, NOW)
    with pytest.raises(NoSuchSuggestion):
        dismiss_suggestion(session, 99, frank.id, NOW)


def test_suggesting_adding_and_dismissing_go_into_the_items_history(
    session: Session, vic: User, frank: User
) -> None:
    black = product(session, "Black", threshold=0)
    added = suggest(session, black, None, 2, vic.id, NOW)
    dismissed = suggest(session, black, None, 1, vic.id, NOW + timedelta(minutes=1))
    dismiss_suggestion(session, dismissed.id, frank.id, NOW + timedelta(minutes=2))
    add_suggestion(session, added.id, frank.id, LATER)

    [item] = shopping_list.read(session).not_in_catalog

    assert item.shopping_history == [
        ShoppingHistoryEntry(ShoppingAction.SUGGESTION_ADDED, 2, None, 0, "frank", LATER),
        ShoppingHistoryEntry(
            ShoppingAction.SUGGESTION_DISMISSED, 1, None, 0, "frank", NOW + timedelta(minutes=2)
        ),
        ShoppingHistoryEntry(
            ShoppingAction.SUGGESTED, 1, None, 0, "vic", NOW + timedelta(minutes=1)
        ),
        ShoppingHistoryEntry(ShoppingAction.SUGGESTED, 2, None, 0, "vic", NOW),
    ]


def test_a_suggested_catalog_colors_history_starts_on_the_product_add_makes(
    session: Session, vic: User, frank: User
) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    suggestion = suggest(session, None, "jade", 3, vic.id, NOW)

    add_suggestion(session, suggestion.id, frank.id, LATER)

    [line] = shopping_list.read(session).lines
    assert line.items[0].shopping_history == [
        ShoppingHistoryEntry(ShoppingAction.SUGGESTION_ADDED, 3, None, 0, "frank", LATER),
        ShoppingHistoryEntry(ShoppingAction.SUGGESTED, 3, None, 0, "vic", NOW),
    ]
