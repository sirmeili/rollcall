"""Values shared by the database, the state machine and the API."""

from enum import StrEnum


class SpoolState(StrEnum):
    SEALED = "sealed"
    OPEN = "open"
    EMPTY = "empty"


class EventType(StrEnum):
    RECEIVED = "received"
    OPENED = "opened"
    EMPTY = "empty"
    REVERT = "revert"


class EventSource(StrEnum):
    SCANNER = "scanner"
    UI = "ui"
    AMS = "ams"


class Role(StrEnum):
    """Web app roles. Each role can do everything the roles before it can."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return list(Role).index(self)

    def allows(self, needed: "Role") -> bool:
        return self.rank >= needed.rank


class Priority(StrEnum):
    """How soon a print request is wanted, most pressing first."""

    URGENT = "urgent"
    NORMAL = "normal"
    NO_RUSH = "no_rush"

    @property
    def rank(self) -> int:
        return list(Priority).index(self)


class RequestStatus(StrEnum):
    """Where a print request is. #76 adds the rest of the pipeline."""

    SUBMITTED = "submitted"


class HistoryKind(StrEnum):
    """What one request history entry records."""

    SUBMITTED = "submitted"
    EDITED = "edited"
    PRIORITY_CHANGED = "priority_changed"


class ModelFileKind(StrEnum):
    """What a print request's model file is, judged from its contents."""

    THREE_MF = "3mf"
    STL = "stl"


class ModelSource(StrEnum):
    """What a print request has for its model: a file, a link, both, or only its notes."""

    FILE = "file"
    LINK = "link"
    BOTH = "both"
    NOTES_ONLY = "notes"


class ChoiceKind(StrEnum):
    """What a filament choice is: an in-stock product or a catalog color."""

    PRODUCT = "product"
    CATALOG_COLOR = "catalog_color"
