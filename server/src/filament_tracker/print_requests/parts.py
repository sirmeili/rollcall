"""The parts of the app Print Requests uses, built once at start and handed to every
`PrintRequests` (ADR-0023)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.db.types import utcnow
from filament_tracker.notifications.notifier import Notifier
from filament_tracker.print_requests.files import ModelFiles
from filament_tracker.print_requests.photos import Photos


class Clock:
    """Now, and today in the server's time zone, which needed-by dates are judged in. Tests
    can give one that answers a fixed time."""

    def __init__(self, time_zone: Callable[[], str]) -> None:
        self._time_zone = time_zone

    def now(self) -> datetime:
        return utcnow()

    def today(self) -> date:
        return datetime.now(ZoneInfo(self._time_zone())).date()


@dataclass(frozen=True)
class Parts:
    notifier: Notifier
    model_files: ModelFiles
    # Photos of finished prints, kept beside the model files.
    photos: Photos
    settings: SettingsStore
    clock: Clock
