"""Print Requests' one interface (ADR-0023).

A `PrintRequests` is made for each HTTP request around its database session, with the app's
parts built once at start. Each action takes the caller and plain inputs, checks every
permission itself and returns plain dataclasses already filtered for the caller. Every
refusal is a `Refused`. The inputs' dataclasses and their limits are here too, for the
routes to check a body against. Each group of actions lives in its own module: reading, requesting,
moving, changing photos and changing holds.
"""

from filament_tracker.db.request_models import (
    CHOICE_NOTE_MAX,
    FILE_NAME_MAX,
    LINK_MAX,
    NOTES_MAX,
    TITLE_MAX,
)
from filament_tracker.print_requests.changing_holds import ChangingHolds
from filament_tracker.print_requests.changing_photos import ChangingPhotos, PhotoUpload, StoredPhoto
from filament_tracker.print_requests.choices import ChoiceInput
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.moving import Moving
from filament_tracker.print_requests.parts import Clock, Parts
from filament_tracker.print_requests.photos import MAX_PHOTOS
from filament_tracker.print_requests.read import Tab
from filament_tracker.print_requests.reading import Reading
from filament_tracker.print_requests.refused import Kind, Refused
from filament_tracker.print_requests.requesting import ModelUpload, Requesting, StoredModel
from filament_tracker.print_requests.rules import RequestFields
from filament_tracker.print_requests.views import (
    AllowedMove,
    ChoiceDetail,
    HistoryEntry,
    Hold,
    ModelFile,
    Photo,
    RequestDetail,
    Requester,
    RequestRow,
    ShoppingStage,
    Swatch,
)


class PrintRequests(Reading, Requesting, Moving, ChangingPhotos, ChangingHolds):
    """Everything a person can do to print requests, and reading them."""


__all__ = [
    "CHOICE_NOTE_MAX",
    "FILE_NAME_MAX",
    "LINK_MAX",
    "MAX_PHOTOS",
    "NOTES_MAX",
    "TITLE_MAX",
    "AllowedMove",
    "ChoiceDetail",
    "ChoiceInput",
    "Clock",
    "Gate",
    "HistoryEntry",
    "Hold",
    "Kind",
    "ModelFile",
    "ModelUpload",
    "Parts",
    "Photo",
    "PhotoUpload",
    "PrintRequests",
    "Refused",
    "RequestFields",
    "RequestDetail",
    "RequestRow",
    "Requester",
    "ShoppingStage",
    "StoredModel",
    "StoredPhoto",
    "Swatch",
    "Tab",
]
