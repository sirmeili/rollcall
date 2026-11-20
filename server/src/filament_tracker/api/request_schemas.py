"""Request and response bodies for print requests."""

from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from filament_tracker.api.schemas import Strict
from filament_tracker.db.request_models import CHOICE_NOTE_MAX, LINK_MAX, NOTES_MAX, TITLE_MAX
from filament_tracker.domain.enums import (
    ChoiceKind,
    HistoryKind,
    ModelFileKind,
    ModelSource,
    Priority,
    RequestStatus,
)

# More than anyone would pick; it only stops absurd input.
MAX_CHOICES = 20


class ChoiceIn(Strict):
    """Exactly one of a product or a catalog color (its OFDB UUID)."""

    product_id: int | None = None
    catalog_color: Annotated[str, StringConstraints(max_length=36)] | None = None
    note: Annotated[str, StringConstraints(max_length=CHOICE_NOTE_MAX)] = ""

    @model_validator(mode="after")
    def one_of(self) -> Self:
        if (self.product_id is None) == (self.catalog_color is None):
            raise ValueError("give a product_id or a catalog_color, not both")
        return self


class RequestIn(Strict):
    """A new request, or an edit (every field again). The rules beyond these limits are
    checked together and reported as `problems`."""

    title: Annotated[str, StringConstraints(max_length=TITLE_MAX)]
    notes: Annotated[str, StringConstraints(max_length=NOTES_MAX)] = ""
    quantity: int = 1
    needed_by: date | None = None
    priority: Priority = Priority.NORMAL
    link: Annotated[str, StringConstraints(max_length=LINK_MAX)] | None = None
    choices: Annotated[list[ChoiceIn], Field(max_length=MAX_CHOICES)]
    # A checked upload to save as the model file, replacing any it has.
    upload_id: UUID | None = None


class RequestEdit(RequestIn):
    # Take the model file off the request.
    remove_file: bool = False


class PriorityIn(Strict):
    priority: Priority


class MoveIn(Strict):
    """A move to another request status, naming the status the caller saw it in."""

    from_status: RequestStatus
    to_status: RequestStatus
    # A note, or the reason a move needs; trimmed, and checked against the move.
    note: str = ""


class MoveOut(BaseModel):
    """A move the caller may make now."""

    to_status: RequestStatus
    # The note is a reason, which may not be left empty.
    reason_required: bool


class RequesterOut(BaseModel):
    id: int
    username: str


class ModelFileOut(BaseModel):
    name: str
    size: int
    kind: ModelFileKind
    # Not on disk (say, after restoring onto a fresh volume): it can't be downloaded.
    missing: bool


class UploadOut(BaseModel):
    id: UUID
    name: str
    size: int
    kind: ModelFileKind


class SimilarOut(BaseModel):
    product_id: int
    name: str
    hex: str
    material: str
    delta_e: float
    sealed: int
    open: int
    different_material: bool


class ChoiceOut(BaseModel):
    kind: ChoiceKind
    note: str
    # The product's name, or the catalog color's name and line.
    name: str
    # RRGGBB, the main color first.
    hexes: list[str]
    material: str | None
    # A product's, with its Sealed and Open spool counts now.
    product_id: int | None
    sealed: int | None
    open: int | None
    # A catalog color's.
    catalog_color: str | None
    # The catalog color's own name ("Black") and its filament line ("PLA Basic").
    color_name: str | None
    line: str | None
    bambu_code: str | None
    # False: no longer in the catalog.
    in_catalog: bool
    multi_color: bool
    # Similar in-stock colors; empty for a multi-color one.
    similar: list[SimilarOut]


class SwatchOut(BaseModel):
    name: str
    hexes: list[str]


class HistoryOut(BaseModel):
    kind: HistoryKind
    username: str | None
    at: datetime
    # An edit's changed fields: title, quantity, needed_by, priority, link, notes, file,
    # filament.
    fields: list[str] | None
    # A priority change's old and new priority, or a status change's old and new status.
    from_value: str | None
    to_value: str | None
    note: str | None


class RequestRowOut(BaseModel):
    id: int
    title: str
    quantity: int
    needed_by: date | None
    priority: Priority
    status: RequestStatus
    requester: RequesterOut
    # What it has for the model: file, link, both or notes (only).
    model: ModelSource
    choices: list[SwatchOut]
    created_at: datetime


class RequestOut(BaseModel):
    id: int
    title: str
    notes: str
    quantity: int
    needed_by: date | None
    priority: Priority
    link: str | None
    status: RequestStatus
    requester: RequesterOut
    file: ModelFileOut | None
    choices: list[ChoiceOut]
    # Newest first.
    history: list[HistoryOut]
    created_at: datetime
    updated_at: datetime
    # What the caller may do to it now.
    can_edit: bool
    can_change_priority: bool
    # The moves the caller may make, the main next step first.
    moves: list[MoveOut]
    # Which try at printing it this is: 1, plus 1 for each Reprint.
    attempt: int
    # The store Find in store searches, without a trailing slash.
    store_address: str


class SubmittedCountOut(BaseModel):
    submitted: int
