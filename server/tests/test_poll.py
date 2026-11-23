"""The database poll keeps going when something goes wrong: a failing listener doesn't stop
the others, and a database problem is logged and tried again on the next poll."""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Product, Spool
from filament_tracker.domain.enums import SpoolState
from filament_tracker.poll import Changes, Poll


def _goes_low(engine: Engine, poll: Poll) -> None:
    """A product goes low between two polls."""
    sessions = create_session_factory(engine)
    with sessions() as session:
        product = Product(
            material_id="GFA00",
            variant_id="A00-K00",
            filament_type="PLA",
            color_rgba="000000FF",
            display_name="Black PLA Basic",
        )
        session.add(product)
        session.flush()
        session.add(Spool(product_id=product.id, state=SpoolState.SEALED))
        session.commit()
        poll.step()
        product.low_stock_threshold = 1
        session.commit()
    poll.step()


def test_a_failing_listener_doesnt_stop_the_others(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    told: list[Changes] = []

    def broken(session: Session, changes: Changes) -> None:
        raise RuntimeError("mail server on fire")

    def listening(session: Session, changes: Changes) -> None:
        told.append(changes)

    _goes_low(engine, Poll(create_session_factory(engine), [broken, listening]))

    assert [p.name for c in told for p in c.became_low] == ["Black PLA Basic"]
    assert "mail server on fire" in caplog.text


def test_a_database_problem_is_logged_and_skipped(caplog: pytest.LogCaptureFixture) -> None:
    def broken() -> Session:
        raise RuntimeError("database is locked")

    Poll(broken, []).step()  # type: ignore[arg-type]

    assert "could not read the database" in caplog.text
