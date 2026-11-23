"""The stale-endpoint sweep: a phone's endpoint with no success in 30 days is dropped, counted
from its last success, or from when it was registered if it never had one. It runs in a
background thread like the catalog sync (ADR-0005): at start, then every hour.

The app sends its endpoint again on every start and sign-in, and the same endpoint keeps
its history (api/push.py), so a dropped phone that is still in use registers again the next
time the app starts.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.db.types import utcnow

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(days=30)
SWEEP_SECONDS = 3600.0
STOP_TIMEOUT = 5.0


def drop_stale(session: Session, now: datetime) -> list[str]:
    """Drop every endpoint with no success in 30 days; the devices whose were dropped."""
    cutoff = now - STALE_AFTER
    last = func.coalesce(PushEndpoint.last_success_at, PushEndpoint.registered_at)
    dropped = []
    for endpoint in session.scalars(select(PushEndpoint).where(last <= cutoff)):
        dropped.append(endpoint.device_id)
        session.delete(endpoint)
    session.commit()
    return dropped


class StaleSweep:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = utcnow,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._stopped = threading.Event()
        # Waits up to the given seconds; True means stop.
        self._wait = wait or self._stopped.wait
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="push-stale-sweep", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT)

    def run(self) -> None:
        while True:
            self._sweep()
            if self._wait(SWEEP_SECONDS):
                return

    def _sweep(self) -> None:
        try:
            with self._sessions() as session:
                dropped = drop_stale(session, self._clock())
        except Exception:
            logger.exception("could not drop stale phone endpoints")
            return
        for device_id in dropped:
            logger.info("phone %s had no success in 30 days, so it was dropped", device_id)
