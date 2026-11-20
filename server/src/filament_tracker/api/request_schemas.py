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
from filament_tracker.print_requests.photos import MAX_PHOTOS

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
    # Photo uploads to save with a move that takes photos (Done).
    photo_ids: Annotated[list[UUID], Field(max_length=MAX_PHOTOS)] = []
    # Approve: the grams for each filament choice, by choice ID; checked by the move.
    grams: Annotated[dict[int, int], Field(max_length=MAX_CHOICES)] = {}


class MoveOut(BaseModel):
    """A move the caller may make now."""

    to_status: RequestStatus
    # The note is a reason, which may not be left empty.
    reason_required: bool
    # Up to 4 photos may be saved with it.
    photos: bool


class PhotosIn(Strict):
    """Photo uploads to save with a Done or Picked Up request."""

    photo_ids: Annotated[list[UUID], Field(min_length=1, max_length=MAX_PHOTOS)]


class PhotoOut(BaseModel):
    """A photo of the finished print. Its `id` names it in the photo's address."""

    id: UUID
    name: str
    uploaded_at: datetime


class PhotoUploadOut(BaseModel):
    id: UUID
    name: str


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


class HoldOut(BaseModel):
    """Grams held on one spool."""

    spool_id: int
    product_id: int
    product_name: str
    grams: int


class ChoiceOut(BaseModel):
    # Names the choice in Approve's grams.
    id: int
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
    # The grams for the whole quantity, from Approve; None until then.
    grams: int | None
    # Grams not yet held, while the request is Approved, Waiting on Filament or Queued.
    short_g: int | None
    # Its holds, for Editors and Admins only; None for anyone else.
    holds: list[HoldOut] | None
    # Grams not held of the product it would be held on (0 with none).
    available_g: int


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
    # Made by RollCall itself, with no user, such as the move on after Approve.
    automatic: bool


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
    # Oldest first.
    photos: list[PhotoOut]
    choices: list[ChoiceOut]
    # Newest first.
    history: list[HistoryOut]
    created_at: datetime
    updated_at: datetime
    # What the caller may do to it now.
    can_edit: bool
    can_change_priority: bool
    # Add and remove photos: a signed-in Admin, while the request is Done or Picked Up.
    can_change_photos: bool
    # The moves the caller may make, the main next step first.
    moves: list[MoveOut]
    # Which try at printing it this is: 1, plus 1 for each Reprint.
    attempt: int
    # The store Find in store searches, without a trailing slash.
    store_address: str


class SubmittedCountOut(BaseModel):
    submitted: int
