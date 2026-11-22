"""Inventory's shopping list service, called directly with a fake request-needs reader: the
print requests short of a product, how their grams turn into spools, and the size an item
uses to turn them."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from test_shopping_list_service import catalog_line, product

from filament_tracker.auth import Principal
from filament_tracker.db.catalog_models import CatalogSize
from filament_tracker.db.models import Product, Spool, User
from filament_tracker.domain.enums import Role, ShoppingAction, SpoolState
from filament_tracker.services import shopping_list
from filament_tracker.services.accounts import create_user
from filament_tracker.services.shopping_list import (
    HandAdded,
    LowStock,
    NetWeight,
    RequestShort,
    ShoppingListItem,
    SizeFrom,
    add_by_hand,
    set_size,
)

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
VIEWER = Principal()


class FakeNeeds:
    """A request-needs reader that answers what it was given, and notes who asked."""

    def __init__(self, needs: Mapping[int, list[RequestShort]]) -> None:
        self.needs = needs
        self.asked: list[Principal] = []

    def __call__(self, session: Session, viewer: Principal) -> dict[int, list[RequestShort]]:
        self.asked.append(viewer)
        return dict(self.needs)


@pytest.fixture
def frank(session: Session) -> User:
    return create_user(session, "frank", "a long enough password", Role.EDITOR)


def short(request_id: int, grams: int, title: str | None = "Lamp shade") -> RequestShort:
    return RequestShort(request_id=request_id, title=title, short_g=grams)


def listed(session: Session, needs: Mapping[int, list[RequestShort]]) -> list[ShoppingListItem]:
    found = shopping_list.read(session, VIEWER, FakeNeeds(needs))
    return [item for line in found.lines for item in line.items] + found.not_in_catalog


def only(session: Session, needs: Mapping[int, list[RequestShort]]) -> ShoppingListItem:
    [item] = listed(session, needs)
    return item


def received(session: Session, item: Product, net_weight_g: int | None, days_ago: int) -> None:
    session.add(
        Spool(
            product=item,
            state=SpoolState.SEALED,
            net_weight_g=net_weight_g,
            received_at=NOW - timedelta(days=days_ago),
        )
    )
    session.flush()


def sizes(session: Session, color: str, *weights: float, refill: bool = False) -> None:
    """More sizes of a catalog color, beside the 1000 g one `catalog_line` gives it, which is
    taken away first."""
    session.query(CatalogSize).filter_by(variant_uuid=color).delete()
    for i, weight in enumerate(weights):
        session.add(
            CatalogSize(
                uuid=f"size-{color}-{i}", variant_uuid=color, filament_weight=weight, refill=refill
            )
        )
    session.flush()


def test_the_reader_is_asked_for_the_viewing_user(session: Session) -> None:
    needs = FakeNeeds({})
    viewer = Principal()

    shopping_list.read(session, viewer, needs)

    [asked] = needs.asked
    assert asked is viewer


def test_two_requests_short_300_g_each_on_a_1000_g_product_need_1_spool(
    session: Session,
) -> None:
    black = product(session, "Black", threshold=0)

    item = only(session, {black.id: [short(1, 300), short(2, 300)]})

    assert item.to_buy == 1
    assert item.reasons == [short(1, 300), short(2, 300)]


def test_request_grams_are_summed_then_rounded_up_once(session: Session) -> None:
    black = product(session, "Black", threshold=0)

    item = only(session, {black.id: [short(1, 600), short(2, 600), short(3, 1)]})

    assert item.to_buy == 2


def test_low_stock_and_hand_added_spools_add_on_top_of_the_requests_spools(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=1)
    add_by_hand(session, black, 2, frank.id, NOW)

    item = only(session, {black.id: [short(1, 300, None)]})

    assert item.to_buy == 1 + 2 + 2
    assert item.reasons == [
        LowStock(spools=2, sealed=0, threshold=1),
        short(1, 300, None),
        HandAdded(item.reasons[2].id, 2, "frank", NOW),  # type: ignore[union-attr]
    ]


def test_a_product_with_no_request_short_of_it_is_left_off(session: Session) -> None:
    product(session, "Black", threshold=0)

    assert listed(session, {}) == []


def test_without_a_reader_there_are_no_request_reasons(session: Session) -> None:
    product(session, "Black", threshold=1)

    [item] = shopping_list.read(session).not_in_catalog

    assert item.reasons == [LowStock(spools=2, sealed=0, threshold=1)]


def test_with_nothing_else_the_size_is_1000_g(session: Session) -> None:
    black = product(session, "Black", threshold=0)

    item = only(session, {black.id: [short(1, 1001)]})

    assert item.size == NetWeight(1000, SizeFrom.DEFAULT)
    assert item.to_buy == 2


def test_a_catalog_colors_1000_g_size_comes_before_its_others(session: Session) -> None:
    catalog_line(session, "PLA Basic", {"jade": None})
    sizes(session, "jade", 250, 1000, 3000, refill=True)
    jade = product(session, "Jade", threshold=0, color="jade")

    item = only(session, {jade.id: [short(1, 1500)]})

    assert item.size == NetWeight(1000, SizeFrom.CATALOG)
    assert item.to_buy == 2


def test_a_catalog_colors_only_size_is_used_without_a_1000_g_one(session: Session) -> None:
    catalog_line(session, "PLA Basic", {"jade": None})
    sizes(session, "jade", 3000)
    jade = product(session, "Jade", threshold=0, color="jade")

    item = only(session, {jade.id: [short(1, 3500)]})

    assert item.size == NetWeight(3000, SizeFrom.CATALOG)
    assert item.to_buy == 2


def test_a_catalog_colors_smallest_size_is_used_without_a_1000_g_one(session: Session) -> None:
    catalog_line(session, "PLA Basic", {"jade": None})
    sizes(session, "jade", 3000, 500, 750)
    jade = product(session, "Jade", threshold=0, color="jade")

    item = only(session, {jade.id: [short(1, 600)]})

    assert item.size == NetWeight(500, SizeFrom.CATALOG)
    assert item.to_buy == 2


def test_a_catalog_color_with_no_sizes_uses_1000_g(session: Session) -> None:
    catalog_line(session, "PLA Basic", {"jade": None})
    sizes(session, "jade")
    jade = product(session, "Jade", threshold=0, color="jade")

    assert only(session, {jade.id: [short(1, 600)]}).size == NetWeight(1000, SizeFrom.DEFAULT)


def test_the_most_recently_received_spools_net_weight_comes_before_the_catalog(
    session: Session,
) -> None:
    catalog_line(session, "PLA Basic", {"jade": None})
    jade = product(session, "Jade", threshold=0, color="jade")
    received(session, jade, 500, days_ago=1)
    received(session, jade, 250, days_ago=9)
    # Never received: no help.
    session.add(Spool(product=jade, state=SpoolState.SEALED, net_weight_g=3000))
    session.flush()

    item = only(session, {jade.id: [short(1, 600)]})

    assert item.size == NetWeight(500, SizeFrom.LAST_SPOOL)
    assert item.to_buy == 2


def test_a_received_spool_with_no_net_weight_is_passed_over(session: Session) -> None:
    jade = product(session, "Jade", threshold=0)
    received(session, jade, None, days_ago=1)
    received(session, jade, 750, days_ago=5)

    assert only(session, {jade.id: [short(1, 600)]}).size == NetWeight(750, SizeFrom.LAST_SPOOL)


def test_a_chosen_size_comes_first_and_re_rounds_only_the_requests_part(
    session: Session, frank: User
) -> None:
    black = product(session, "Black", threshold=1)
    received(session, black, 1000, days_ago=1)
    add_by_hand(session, black, 1, frank.id, NOW)
    needs = {black.id: [short(1, 2500)]}
    assert only(session, needs).to_buy == 1 + 3 + 1

    set_size(session, black, 3000, frank.id, NOW)

    item = only(session, needs)
    assert item.size == NetWeight(3000, SizeFrom.CHOSEN)
    assert item.to_buy == 1 + 1 + 1


def test_choosing_a_size_goes_into_the_history(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=1)

    set_size(session, black, 3000, frank.id, NOW)

    [entry] = only(session, {}).history
    assert (entry.action, entry.size_g, entry.spools, entry.on_order, entry.by, entry.at) == (
        ShoppingAction.SIZE_CHANGED,
        3000,
        None,
        0,
        "frank",
        NOW,
    )


def test_choosing_a_size_again_replaces_it(session: Session, frank: User) -> None:
    black = product(session, "Black", threshold=0)
    set_size(session, black, 3000, frank.id, NOW)

    set_size(session, black, 250, None, NOW)

    item = only(session, {black.id: [short(1, 600)]})
    assert item.size == NetWeight(250, SizeFrom.CHOSEN)
    assert item.to_buy == 3
    assert [e.by for e in item.history] == [None, "frank"]
