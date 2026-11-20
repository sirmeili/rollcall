"""A cooldown: one attempt per gap, for the whole server.

Kept in memory, like the sign-in throttle (services/throttle.py); a restart clears it.
"""

import time
from collections.abc import Callable

# Send test email: one test every 30 seconds, whatever its result.
TEST_EMAIL_GAP = 30.0


class Cooldown:
    def __init__(self, gap: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.gap = gap
        self.clock = clock
        self._last: float | None = None

    def start(self) -> bool:
        """Count an attempt now, or return False when the last one was under `gap` ago."""
        now = self.clock()
        if self._last is not None and now - self._last < self.gap:
            return False
        self._last = now
        return True
