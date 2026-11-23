"""The database poll (ADR-0009): every few seconds, read what stock looks like and hand what
changed since the last poll to whoever acts on it (notifications, Home Assistant events).

It always runs, whether or not Home Assistant is set up. The first poll after start only
records where things stand, so a restart tells nobody about what was already so.
"""

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.ha.snapshot import ProductState, take_snapshot

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0
STOP_TIMEOUT = 5.0


@dataclass(frozen=True)
class Changes:
    """What changed since the last poll."""

    # Products that went from not low to low stock.
    became_low: tuple[ProductState, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.became_low)


# Acts on the changes, reading anything else it needs in the poll's session.
Listener = Callable[[Session, Changes], None]


class StockWatch:
    """Where things stood at the last poll, to tell what changed. Not thread-safe."""

    def __init__(self) -> None:
        self._low: set[int] | None = None  # None before the first poll

    def changes(self, session: Session) -> Changes:
        low_now = take_snapshot(session).low_stock
        before, self._low = self._low, {p.id for p in low_now}
        if before is None:
            return Changes()
        return Changes(became_low=tuple(p for p in low_now if p.id not in before))


class Poll:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        listeners: Sequence[Listener],
        *,
        poll_seconds: float = POLL_SECONDS,
    ) -> None:
        self._sessions = session_factory
        self._listeners = tuple(listeners)
        self._poll_seconds = poll_seconds
        self._watch = StockWatch()
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="poll", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT)

    def _run(self) -> None:
        while not self._stopping.is_set():
            self.step()
            self._stopping.wait(self._poll_seconds)

    def step(self) -> None:
        """One poll: see what changed and hand it to each listener. One at a time."""
        with self._lock:
            try:
                with self._sessions() as session:
                    changes = self._watch.changes(session)
                    if changes:
                        self._tell(session, changes)
            except Exception:
                logger.exception("database poll: could not read the database")

    def _tell(self, session: Session, changes: Changes) -> None:
        for listener in self._listeners:
            try:
                listener(session, changes)
            except Exception:
                logger.exception("database poll: %r failed", listener)
