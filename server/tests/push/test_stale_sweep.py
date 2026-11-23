"""The stale-endpoint sweep: a failing phone's endpoint (a notification to it given up since
its last success) with no success in 30 days (since it was registered, when it never had one)
is dropped, at start and then every hour. A quiet phone, never failing, is kept however long
nothing was sent to it."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Device, User
from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.domain.enums import PushRoute, Role
from filament_tracker.push.stale import SWEEP_SECONDS, StaleSweep

NOW = datetime.fromisoformat("2026-11-23T12:00:00+00:00")
DAY = timedelta(days=1)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def _phone(
    sessions: sessionmaker[Session],
    device_id: str,
    registered: datetime,
    success: datetime | None = None,
    *,
    failing: bool = True,
) -> None:
    """A user's phone; failing unless `failing` is False: a notification to it was given up
    since its last success."""
    with sessions() as session:
        user = User(username=device_id, password_hash="x", role=Role.VIEWER)  # noqa: S106 - test value
        session.add(Device(id=device_id, name=device_id, token_hash=device_id, user=user))
        session.add(
            PushEndpoint(
                device_id=device_id,
                route=PushRoute.FCM,
                endpoint=f"token-{device_id}",
                registered_at=registered,
                last_success_at=success,
                failures=1 if failing else 0,
                failing_since=registered + DAY if failing else None,
            )
        )
        session.commit()


def _kept(sessions: sessionmaker[Session]) -> set[str]:
    with sessions() as session:
        return {e.device_id for e in session.query(PushEndpoint)}


def _sweep_once(sessions: sessionmaker[Session]) -> None:
    StaleSweep(sessions, clock=lambda: NOW, wait=lambda seconds: True).run()


def test_a_quiet_phone_with_no_failures_is_kept(sessions: sessionmaker[Session]) -> None:
    _phone(sessions, "never-sent", NOW - 90 * DAY, failing=False)
    _phone(sessions, "quiet-since", NOW - 90 * DAY, success=NOW - 60 * DAY, failing=False)

    _sweep_once(sessions)

    assert _kept(sessions) == {"never-sent", "quiet-since"}


def test_a_failing_endpoint_with_no_success_in_30_days_is_dropped(
    sessions: sessionmaker[Session],
) -> None:
    _phone(sessions, "old-success", NOW - 90 * DAY, success=NOW - 30 * DAY)
    _phone(sessions, "recent-success", NOW - 90 * DAY, success=NOW - 29 * DAY)
    _phone(sessions, "never-old", NOW - 30 * DAY)
    _phone(sessions, "never-new", NOW - 29 * DAY)

    _sweep_once(sessions)

    assert _kept(sessions) == {"recent-success", "never-new"}


def test_it_sweeps_at_start_then_every_hour(sessions: sessionmaker[Session]) -> None:
    waits: list[float] = []
    clock = iter([NOW, NOW + 10 * DAY])

    def wait(seconds: float) -> bool:
        waits.append(seconds)
        if len(waits) == 1:
            _phone(sessions, "phone", NOW - 25 * DAY)
            return False
        return True

    StaleSweep(sessions, clock=lambda: next(clock), wait=wait).run()

    assert waits == [SWEEP_SECONDS, SWEEP_SECONDS]
    assert _kept(sessions) == set()


def test_a_failing_sweep_is_logged_and_tried_again(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    def broken() -> Session:
        raise RuntimeError("no database")

    calls: list[float] = []

    def wait(seconds: float) -> bool:
        calls.append(seconds)
        return len(calls) == 2

    StaleSweep(broken, clock=lambda: NOW, wait=wait).run()  # type: ignore[arg-type]

    assert len(calls) == 2
    assert "stale phone endpoints" in caplog.text


def test_it_starts_and_stops(sessions: sessionmaker[Session]) -> None:
    _phone(sessions, "phone", NOW - 31 * DAY)
    sweep = StaleSweep(sessions, clock=lambda: NOW)

    sweep.start()
    sweep.stop()

    assert _kept(sessions) == set()
