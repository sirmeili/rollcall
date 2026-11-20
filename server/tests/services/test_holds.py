"""Inventory's hold service, called directly: where holds go, how they split, what is left
short, and the available-grams arithmetic. Holders are named only by type and ID."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from filament_tracker.db.models import Product, Spool
from filament_tracker.domain.enums import ReleaseReason, SpoolState
from filament_tracker.services import holds
from filament_tracker.services.holds import Holder

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 21, 15, 30, tzinfo=UTC)
FIRST = Holder("filament_choice", 1)
SECOND = Holder("filament_choice", 2)


@pytest.fixture
def black(session: Session) -> Product:
    product = Product(
        material_id="GFA00",
        variant_id="A00-K00",
        filament_type="PLA",
        color_rgba="000000FF",
        display_name="Black PLA Basic",
    )
    session.add(product)
    session.flush()
    return product


def spool(
    session: Session, product: Product, state: SpoolState | None, grams_left: int | None
) -> Spool:
    item = Spool(product=product, state=state, net_weight_g=1000, grams_left_g=grams_left)
    session.add(item)
    session.flush()
    return item


def held(session: Session, holder: Holder) -> list[tuple[int, int]]:
    return [(hold.spool_id, hold.grams) for hold in holds.active_holds(session, holder)]


def test_open_spools_are_held_first_least_grams_left_first_then_sealed(
    session: Session, black: Product
) -> None:
    sealed_small = spool(session, black, SpoolState.SEALED, 500)
    open_big = spool(session, black, SpoolState.OPEN, 400)
    open_small = spool(session, black, SpoolState.OPEN, 100)

    placed = holds.place(session, FIRST, black.id, 800, NOW)

    assert placed == holds.Placed(held=800, short=0)
    assert held(session, FIRST) == [
        (open_small.id, 100),
        (open_big.id, 400),
        (sealed_small.id, 300),
    ]


def test_a_spool_that_covers_the_grams_is_held_alone(session: Session, black: Product) -> None:
    only = spool(session, black, SpoolState.OPEN, 600)
    spool(session, black, SpoolState.SEALED, 1000)

    assert holds.place(session, FIRST, black.id, 250, NOW) == holds.Placed(held=250, short=0)
    assert held(session, FIRST) == [(only.id, 250)]


def test_too_little_is_held_as_a_partial_cover_and_the_rest_is_short(
    session: Session, black: Product
) -> None:
    first = spool(session, black, SpoolState.OPEN, 150)
    second = spool(session, black, SpoolState.SEALED, 200)

    assert holds.place(session, FIRST, black.id, 500, NOW) == holds.Placed(held=350, short=150)
    assert held(session, FIRST) == [(first.id, 150), (second.id, 200)]
    assert holds.shortfall(session, FIRST, 500) == 150


def test_open_spools_with_unknown_grams_and_gone_spools_are_never_held(
    session: Session, black: Product
) -> None:
    spool(session, black, SpoolState.OPEN, None)
    spool(session, black, SpoolState.EMPTY, 800)
    spool(session, black, None, 800)

    assert holds.place(session, FIRST, black.id, 100, NOW) == holds.Placed(held=0, short=100)
    assert held(session, FIRST) == []


def test_no_product_holds_nothing_and_leaves_every_gram_short(session: Session) -> None:
    assert holds.place(session, FIRST, None, 300, NOW) == holds.Placed(held=0, short=300)
    assert holds.shortfall(session, FIRST, 300) == 300


def test_other_products_spools_are_not_held(session: Session, black: Product) -> None:
    white = Product(filament_type="PLA", color_rgba="FFFFFFFF", display_name="White PLA Basic")
    session.add(white)
    spool(session, white, SpoolState.OPEN, 900)

    assert holds.place(session, FIRST, black.id, 100, NOW) == holds.Placed(held=0, short=100)


def test_a_second_holder_sees_only_what_the_first_left(session: Session, black: Product) -> None:
    shared = spool(session, black, SpoolState.OPEN, 300)
    sealed = spool(session, black, SpoolState.SEALED, 1000)
    holds.place(session, FIRST, black.id, 200, NOW)

    assert holds.place(session, SECOND, black.id, 400, NOW) == holds.Placed(held=400, short=0)
    assert held(session, SECOND) == [(shared.id, 100), (sealed.id, 300)]
    assert holds.spool_available(session, shared) == 0
    assert holds.spool_available(session, sealed) == 700


def test_available_grams_are_grams_left_less_active_holds(session: Session, black: Product) -> None:
    opened = spool(session, black, SpoolState.OPEN, 600)
    sealed = spool(session, black, SpoolState.SEALED, 1000)
    unknown = spool(session, black, SpoolState.OPEN, None)
    empty = spool(session, black, SpoolState.EMPTY, 500)
    holds.place(session, FIRST, black.id, 250, NOW)

    assert holds.spool_available(session, opened) == 350
    assert holds.spool_available(session, sealed) == 1000
    assert holds.spool_available(session, unknown) is None
    assert holds.spool_available(session, empty) == 0
    assert holds.product_available(session, black.id) == 1350


def test_a_spool_held_beyond_its_grams_left_has_none_available_and_counts_only_what_it_has(
    session: Session, black: Product
) -> None:
    opened = spool(session, black, SpoolState.OPEN, 500)
    holds.place(session, FIRST, black.id, 400, NOW)
    holds.place(session, SECOND, black.id, 100, NOW)
    # The AMS reports less than was held.
    opened.grams_left_g = 300
    session.flush()

    assert holds.spool_available(session, opened) == 0
    assert holds.product_available(session, black.id) == 0
    assert holds.shortfall(session, FIRST, 400) == 100
    assert holds.shortfall(session, SECOND, 100) == 0


def test_a_holder_with_no_holds_is_short_its_whole_target(session: Session) -> None:
    assert holds.shortfall(session, FIRST, 120) == 120


def test_releasing_keeps_the_holds_with_when_and_why_and_frees_their_grams(
    session: Session, black: Product
) -> None:
    opened = spool(session, black, SpoolState.OPEN, 300)
    sealed = spool(session, black, SpoolState.SEALED, 1000)
    holds.place(session, FIRST, black.id, 500, NOW)
    holds.place(session, SECOND, black.id, 100, NOW)

    released = holds.release(session, FIRST, ReleaseReason.FAILED, LATER)

    assert [(h.spool_id, h.grams, h.released_at, h.release_reason) for h in released] == [
        (opened.id, 300, LATER, ReleaseReason.FAILED),
        (sealed.id, 200, LATER, ReleaseReason.FAILED),
    ]
    assert held(session, FIRST) == []
    assert held(session, SECOND) == [(sealed.id, 100)]
    assert holds.product_available(session, black.id) == 1200
    assert holds.release(session, FIRST, ReleaseReason.DONE, LATER) == []
