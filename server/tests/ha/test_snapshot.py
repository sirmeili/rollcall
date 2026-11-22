from datetime import UTC, datetime

from ha_helpers import add_product, add_spools
from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Spool, Tag
from filament_tracker.db.shopping_models import DuplicateCandidate, PossibleDuplicate
from filament_tracker.domain.enums import DuplicateState, EventSource, EventType, SpoolState
from filament_tracker.ha.snapshot import ProductState, take_snapshot


def test_counts_low_stock_and_review(session: Session) -> None:
    black = add_product(session, "Black PLA Basic", low_stock_threshold=2)
    white = add_product(session, "White PETG", filament_type="PETG", color_rgba="FFFFFFFF")
    add_spools(session, black, SpoolState.SEALED, 2)
    add_spools(session, black, SpoolState.OPEN)
    add_spools(session, white, SpoolState.SEALED, 3)
    add_spools(session, white, SpoolState.EMPTY)
    # One of each kind of review item: a flagged event, an unknown tag, a likely-empty spool.
    spool = Spool(product_id=white.id, state=SpoolState.OPEN, remaining_pct=0)
    session.add(spool)
    session.flush()
    session.add(
        Event(
            spool_id=spool.id,
            type=EventType.OPENED,
            source=EventSource.UI,
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
            flagged=True,
        )
    )
    session.add(Tag(uid="0A0B0C0D"))
    session.flush()

    snapshot = take_snapshot(session)

    assert snapshot.products == (
        ProductState(black.id, "Black PLA Basic", "PLA", "000000FF", 2, 1, True, 2),
        ProductState(white.id, "White PETG", "PETG", "FFFFFFFF", 3, 1, False, 0),
    )
    assert (snapshot.total_sealed, snapshot.total_open, snapshot.total_spools) == (5, 2, 7)
    assert [p.name for p in snapshot.low_stock] == ["Black PLA Basic"]
    assert snapshot.in_review == 3


def test_an_empty_database(session: Session) -> None:
    snapshot = take_snapshot(session)
    assert (snapshot.products, snapshot.total_spools, snapshot.in_review) == ((), 0, 0)
    assert snapshot.low_stock == ()


def test_possible_duplicates_waiting_count_in_review(session: Session) -> None:
    scanned = add_product(session, "PLA Basic #050505", color_rgba="050505FF")
    waiting = add_product(
        session, "Black PLA Basic", material_id=None, variant_id=None, from_catalog=True
    )
    for state in (DuplicateState.OPEN, DuplicateState.KEPT_SEPARATE):
        session.add(
            PossibleDuplicate(
                product_id=scanned.id,
                state=state,
                candidates=[DuplicateCandidate(product_id=waiting.id)],
            )
        )
    session.flush()

    assert take_snapshot(session).in_review == 1
