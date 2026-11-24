"""Print Requests' one interface (ADR-0023).

A `PrintRequests` is made for each HTTP request around its database session, with the app's
parts built once at start. Each action takes the caller and plain inputs, checks every
permission itself and returns plain dataclasses already filtered for the caller. Every
refusal is a `Refused`. Each group of actions lives in its own module: reading, requesting,
moving and changing holds.
"""

from filament_tracker.print_requests.changing_holds import ChangingHolds
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.moving import Moving
from filament_tracker.print_requests.parts import Clock, Parts
from filament_tracker.print_requests.read import Tab
from filament_tracker.print_requests.reading import Reading
from filament_tracker.print_requests.refused import Kind, Refused
from filament_tracker.print_requests.requesting import Requesting
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


class PrintRequests(Reading, Requesting, Moving, ChangingHolds):
    """Everything a person can do to print requests, and reading them."""


__all__ = [
    "AllowedMove",
    "ChoiceDetail",
    "Clock",
    "Gate",
    "HistoryEntry",
    "Hold",
    "Kind",
    "ModelFile",
    "Parts",
    "Photo",
    "PrintRequests",
    "Refused",
    "RequestDetail",
    "RequestRow",
    "Requester",
    "ShoppingStage",
    "Swatch",
    "Tab",
]
