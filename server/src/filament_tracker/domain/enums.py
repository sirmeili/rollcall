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


class ReleaseReason(StrEnum):
    """Why a hold was released."""

    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # The spool became Empty or Unknown.
    SPOOL_GONE = "spool_gone"
    # Replaced by a hand change or new grams.
    CHANGED = "changed"


class RequestStatus(StrEnum):
    """Where a print request is. While it goes ahead: Submitted to Picked Up. When it stops:
    Rejected, Cancelled or Failed. The moves between them are in print_requests/pipeline.py."""

    SUBMITTED = "submitted"
    APPROVED = "approved"
    WAITING_ON_FILAMENT = "waiting_on_filament"
    QUEUED = "queued"
    PRINTING = "printing"
    DONE = "done"
    PICKED_UP = "picked_up"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def closed(self) -> bool:
        """Picked Up, Rejected and Cancelled; every other status, Failed too, is open."""
        return self in (RequestStatus.PICKED_UP, RequestStatus.REJECTED, RequestStatus.CANCELLED)


class HistoryKind(StrEnum):
    """What one request history entry records."""

    SUBMITTED = "submitted"
    EDITED = "edited"
    PRIORITY_CHANGED = "priority_changed"
    STATUS_CHANGED = "status_changed"
    PHOTO_ADDED = "photo_added"
    PHOTO_REMOVED = "photo_removed"


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
