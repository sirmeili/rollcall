"""A cooldown: one attempt per gap, for the whole server or for each of several things.

Kept in memory, like the sign-in throttle (services/throttle.py); a restart clears it.
"""

import time
from collections.abc import Callable

# Send test email: one test every 30 seconds, whatever its result.
TEST_EMAIL_GAP = 30.0
# A test phone notification: one every 30 seconds for each phone.
TEST_PUSH_GAP = 30.0


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


class Cooldowns:
    """A cooldown for each key, such as each phone."""

    def __init__(self, gap: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._gap = gap
        self._clock = clock
        self._each: dict[str, Cooldown] = {}

    def start(self, key: str) -> bool:
        """Count an attempt for `key` now, or return False when its last one was under `gap`
        ago."""
        cooldown = self._each.setdefault(key, Cooldown(self._gap, clock=self._clock))
        return cooldown.start()
