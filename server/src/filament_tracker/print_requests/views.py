"""Print requests as a caller sees them: a request's detail and a row of the Requests list,
already filtered for the viewer. Plain dataclasses; the routes map them onto their responses.

Only Editors and Admins see a choice's grams, what it is short, its holds and the grams
available for it. Anyone else is told only whether it is held, and for them a Queued request
is always held: one left short stays Queued.
"""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import FilamentChoice, PrintRequest
from filament_tracker.domain.enums import (
    HistoryKind,
    ModelFileKind,
    ModelSource,
    Priority,
    RequestStatus,
)
from filament_tracker.print_requests import filament, needs
from filament_tracker.print_requests.access import (
    may_change_holds,
    may_change_photos,
    movers,
    sees_every_request,
)
from filament_tracker.print_requests.choices import ChoiceReader, ShownChoice, swatch
from filament_tracker.print_requests.parts import Parts
from filament_tracker.print_requests.pipeline import allowed_moves, attempt
from filament_tracker.print_requests.read import model_source
from filament_tracker.print_requests.service import why_not_editable
from filament_tracker.services import holds, shopping_list
from filament_tracker.services.shopping_list import ItemStage, Stage


@dataclass(frozen=True)
class Requester:
    id: int
    username: str


@dataclass(frozen=True)
class Swatch:
    name: str
    # RRGGBB, the main color first.
    hexes: list[str]


@dataclass(frozen=True)
class RequestRow:
    """A request on the Requests list."""

    id: int
    title: str
    quantity: int
    needed_by: date | None
    priority: Priority
    status: RequestStatus
    requester: Requester
    model: ModelSource
    choices: list[Swatch]
    created_at: datetime


@dataclass(frozen=True)
class ModelFile:
    name: str
    size: int
    kind: ModelFileKind
    # Not on disk (say, after restoring onto a fresh volume): it can't be downloaded.
    missing: bool


@dataclass(frozen=True)
class Photo:
    id: UUID
    name: str
    uploaded_at: datetime


@dataclass(frozen=True)
class Hold:
    """Grams held on one spool for a choice."""

    id: int
    spool_id: int
    product_id: int
    product_name: str
    grams: int


@dataclass(frozen=True)
class ShoppingStage:
    """A short choice's product's shopping list item stage."""

    stage: Stage
    product_id: int
    on_order: int
    need: int


@dataclass(frozen=True)
class ChoiceDetail:
    id: int
    # The choice with the stock and catalog as they are now.
    shown: ShownChoice
    # Held in full, while the request holds filament; else None.
    held: bool | None
    # For Editors and Admins only; None for anyone else.
    grams: int | None
    short_g: int | None
    holds: list[Hold] | None
    available_g: int | None
    # While it is short, for anyone who sees the request.
    shopping: ShoppingStage | None


@dataclass(frozen=True)
class HistoryEntry:
    kind: HistoryKind
    username: str | None
    at: datetime
    fields: list[str] | None
    from_value: str | None
    to_value: str | None
    note: str | None
    automatic: bool


@dataclass(frozen=True)
class AllowedMove:
    """A move the caller may make now."""

    to_status: RequestStatus
    reason_required: bool
    photos: bool


@dataclass(frozen=True)
class RequestDetail:
    """A request as the caller sees it, with what they may do to it now."""

    id: int
    title: str
    notes: str
    quantity: int
    needed_by: date | None
    priority: Priority
    link: str | None
    status: RequestStatus
    requester: Requester
    file: ModelFile | None
    # Oldest first.
    photos: list[Photo]
    choices: list[ChoiceDetail]
    # Newest first.
    history: list[HistoryEntry]
    created_at: datetime
    updated_at: datetime
    may_edit: bool
    may_change_priority: bool
    may_change_photos: bool
    may_change_holds: bool
    # The main next step first.
    moves: list[AllowedMove]
    attempt: int
    store_address: str


def _requester(request: PrintRequest) -> Requester:
    return Requester(id=request.requester.id, username=request.requester.username)


def row_of(request: PrintRequest) -> RequestRow:
    return RequestRow(
        id=request.id,
        title=request.title,
        quantity=request.quantity,
        needed_by=request.needed_by,
        priority=request.priority,
        status=request.status,
        requester=_requester(request),
        model=model_source(request),
        choices=[Swatch(name=n, hexes=h) for n, h in map(swatch, request.choices)],
        created_at=request.created_at,
    )


def _file(request: PrintRequest, parts: Parts) -> ModelFile | None:
    if request.file_stored_name is None or request.file_kind is None:
        return None
    return ModelFile(
        name=request.file_name or "",
        size=request.file_size or 0,
        kind=request.file_kind,
        missing=not parts.model_files.exists(request.file_stored_name),
    )


def _may_edit(caller: Principal, request: PrintRequest) -> bool:
    user = caller.user
    return user is not None and why_not_editable(request, user) is None


def _holds(session: Session, choice: FilamentChoice) -> list[Hold]:
    return [
        Hold(
            id=hold.id,
            spool_id=hold.spool_id,
            product_id=hold.spool.product_id,
            product_name=hold.spool.product.display_name,
            grams=hold.grams,
        )
        for hold in holds.active_holds(session, filament.holder(choice))
    ]


def _held(request: PrintRequest, short: int | None, staff: bool) -> bool | None:
    if short is None:
        return None
    return short == 0 or (not staff and request.status is RequestStatus.QUEUED)


def _stages(
    session: Session, caller: Principal, short: list[FilamentChoice]
) -> dict[int, ItemStage]:
    """The shopping list stage of each short choice's product, by product ID, counting the
    print requests. Reading the list clears the dismissals of products that need nothing any
    more; that is not saved here, since reading a request never writes (ADR-0023): the
    shopping list's own reads clear them again (ADR-0021)."""
    found = {filament.product_id(session, choice) for choice in short}
    product_ids = {product_id for product_id in found if product_id is not None}
    return shopping_list.stages(session, caller, needs.request_needs, product_ids)


def _stage(
    stages: dict[int, ItemStage], session: Session, choice: FilamentChoice
) -> ShoppingStage | None:
    product_id = filament.product_id(session, choice)
    found = stages.get(product_id) if product_id is not None else None
    if found is None:
        return None
    return ShoppingStage(
        stage=found.stage, product_id=found.product_id, on_order=found.on_order, need=found.need
    )


def _history(request: PrintRequest) -> list[HistoryEntry]:
    return [
        HistoryEntry(
            kind=entry.kind,
            username=entry.user.username if entry.user is not None else None,
            at=entry.at,
            fields=entry.fields,
            from_value=entry.from_value,
            to_value=entry.to_value,
            note=entry.note,
            automatic=entry.automatic,
        )
        for entry in reversed(request.history)
    ]


def _choices(
    session: Session, parts: Parts, caller: Principal, request: PrintRequest
) -> list[ChoiceDetail]:
    settings = parts.settings
    reader = ChoiceReader(session, settings.similarity_cutoff(), settings.store_address())
    staff = sees_every_request(caller)
    short_by_choice = filament.request_short(session, request)
    stages = _stages(session, caller, [c for c in request.choices if short_by_choice.get(c.id)])
    found = []
    for choice in request.choices:
        short = short_by_choice.get(choice.id)
        found.append(
            ChoiceDetail(
                id=choice.id,
                shown=reader.show(choice),
                held=_held(request, short, staff),
                grams=choice.grams if staff else None,
                short_g=short if staff else None,
                holds=_holds(session, choice) if staff else None,
                available_g=filament.available(session, choice) if staff else None,
                shopping=_stage(stages, session, choice) if short else None,
            )
        )
    return found


def detail_of(
    session: Session, parts: Parts, caller: Principal, request: PrintRequest
) -> RequestDetail:
    """The request as the caller sees it. Reads only: nothing is saved."""
    return RequestDetail(
        id=request.id,
        title=request.title,
        notes=request.notes,
        quantity=request.quantity,
        needed_by=request.needed_by,
        priority=request.priority,
        link=request.link,
        status=request.status,
        requester=_requester(request),
        file=_file(request, parts),
        photos=[
            Photo(id=photo.id, name=photo.file_name, uploaded_at=photo.uploaded_at)
            for photo in request.photos
        ],
        choices=_choices(session, parts, caller, request),
        history=_history(request),
        created_at=request.created_at,
        updated_at=request.updated_at,
        may_edit=_may_edit(caller, request),
        may_change_priority=sees_every_request(caller) and not request.status.closed,
        may_change_photos=may_change_photos(caller, request),
        may_change_holds=may_change_holds(caller, request),
        moves=[
            AllowedMove(to_status=m.to_status, reason_required=m.needs_reason, photos=m.photos)
            for m in allowed_moves(request, movers(caller, request))
        ],
        attempt=attempt(request),
        store_address=parts.settings.store_address(),
    )
