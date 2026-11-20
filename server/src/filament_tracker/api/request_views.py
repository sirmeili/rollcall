"""Print requests as the API returns them."""

from fastapi import Request
from sqlalchemy.orm import Session

from filament_tracker.api.request_schemas import (
    ChoiceOut,
    HistoryOut,
    ModelFileOut,
    MoveOut,
    RequesterOut,
    RequestOut,
    RequestRowOut,
    SimilarOut,
    SwatchOut,
)
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.auth import Principal
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.print_requests.access import movers, sees_every_request
from filament_tracker.print_requests.choices import ChoiceReader, swatch
from filament_tracker.print_requests.files import ModelFiles
from filament_tracker.print_requests.pipeline import allowed_moves, attempt
from filament_tracker.print_requests.read import model_source
from filament_tracker.print_requests.service import why_not_editable


def model_files(request: Request) -> ModelFiles:
    return request.app.state.model_files


def _store(request: Request) -> SettingsStore:
    return request.app.state.settings_store


def row_out(item: PrintRequest) -> RequestRowOut:
    return RequestRowOut(
        id=item.id,
        title=item.title,
        quantity=item.quantity,
        needed_by=item.needed_by,
        priority=item.priority,
        status=item.status,
        requester=RequesterOut(id=item.requester.id, username=item.requester.username),
        model=model_source(item),
        choices=[SwatchOut(name=n, hexes=h) for n, h in map(swatch, item.choices)],
        created_at=item.created_at,
    )


def _file_out(item: PrintRequest, files: ModelFiles) -> ModelFileOut | None:
    if item.file_stored_name is None or item.file_kind is None:
        return None
    return ModelFileOut(
        name=item.file_name or "",
        size=item.file_size or 0,
        kind=item.file_kind,
        missing=not files.exists(item.file_stored_name),
    )


def can_edit(principal: Principal, item: PrintRequest) -> bool:
    user = principal.user
    return user is not None and why_not_editable(item, user) is None


def request_out(
    http: Request, session: Session, principal: Principal, item: PrintRequest
) -> RequestOut:
    store = _store(http)
    reader = ChoiceReader(session, store.similarity_cutoff(), store.store_address())
    choices = []
    for choice in item.choices:
        shown = reader.show(choice)
        choices.append(
            ChoiceOut(
                kind=shown.kind,
                note=shown.note,
                name=shown.name,
                hexes=shown.hexes,
                material=shown.material,
                product_id=shown.product_id,
                sealed=shown.sealed,
                open=shown.open,
                catalog_color=shown.catalog_color,
                color_name=shown.color_name,
                line=shown.line,
                bambu_code=shown.bambu_code,
                in_catalog=shown.in_catalog,
                multi_color=shown.multi_color,
                similar=[SimilarOut.model_validate(s, from_attributes=True) for s in shown.similar],
            )
        )
    history = [
        HistoryOut(
            kind=entry.kind,
            username=entry.user.username if entry.user is not None else None,
            at=entry.at,
            fields=entry.fields,
            from_value=entry.from_value,
            to_value=entry.to_value,
            note=entry.note,
        )
        for entry in reversed(item.history)
    ]
    return RequestOut(
        id=item.id,
        title=item.title,
        notes=item.notes,
        quantity=item.quantity,
        needed_by=item.needed_by,
        priority=item.priority,
        link=item.link,
        status=item.status,
        requester=RequesterOut(id=item.requester.id, username=item.requester.username),
        file=_file_out(item, model_files(http)),
        choices=choices,
        history=history,
        created_at=item.created_at,
        updated_at=item.updated_at,
        can_edit=can_edit(principal, item),
        can_change_priority=sees_every_request(principal) and not item.status.closed,
        moves=[
            MoveOut(to_status=m.to_status, reason_required=m.needs_reason)
            for m in allowed_moves(item, movers(principal, item))
        ],
        attempt=attempt(item),
        store_address=store.store_address(),
    )
