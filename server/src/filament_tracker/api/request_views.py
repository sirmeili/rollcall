"""Print requests as the API returns them: Print Requests' dataclasses mapped onto the
response schemas."""

from filament_tracker.api.request_schemas import (
    ChoiceOut,
    HistoryOut,
    HoldOut,
    ModelFileOut,
    MoveOut,
    PhotoOut,
    RequesterOut,
    RequestOut,
    RequestRowOut,
    ShoppingStageOut,
    SimilarOut,
    SwatchOut,
)
from filament_tracker.print_requests.interface import (
    ChoiceDetail,
    ModelFile,
    RequestDetail,
    Requester,
    RequestRow,
)


def _requester_out(requester: Requester) -> RequesterOut:
    return RequesterOut(id=requester.id, username=requester.username)


def row_out(row: RequestRow) -> RequestRowOut:
    return RequestRowOut(
        id=row.id,
        title=row.title,
        quantity=row.quantity,
        needed_by=row.needed_by,
        priority=row.priority,
        status=row.status,
        requester=_requester_out(row.requester),
        model=row.model,
        choices=[SwatchOut(name=s.name, hexes=s.hexes) for s in row.choices],
        created_at=row.created_at,
    )


def _file_out(file: ModelFile | None) -> ModelFileOut | None:
    if file is None:
        return None
    return ModelFileOut(name=file.name, size=file.size, kind=file.kind, missing=file.missing)


def _choice_out(choice: ChoiceDetail) -> ChoiceOut:
    shown = choice.shown
    stage = choice.shopping
    return ChoiceOut(
        id=choice.id,
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
        held=choice.held,
        grams=choice.grams,
        short_g=choice.short_g,
        holds=None
        if choice.holds is None
        else [HoldOut.model_validate(h, from_attributes=True) for h in choice.holds],
        available_g=choice.available_g,
        shopping=None
        if stage is None
        else ShoppingStageOut(
            stage=stage.stage,
            product_id=stage.product_id,
            on_order=stage.on_order,
            need=stage.need,
        ),
    )


def request_out(detail: RequestDetail) -> RequestOut:
    return RequestOut(
        id=detail.id,
        title=detail.title,
        notes=detail.notes,
        quantity=detail.quantity,
        needed_by=detail.needed_by,
        priority=detail.priority,
        link=detail.link,
        status=detail.status,
        requester=_requester_out(detail.requester),
        file=_file_out(detail.file),
        photos=[PhotoOut(id=p.id, name=p.name, uploaded_at=p.uploaded_at) for p in detail.photos],
        choices=[_choice_out(choice) for choice in detail.choices],
        history=[HistoryOut.model_validate(h, from_attributes=True) for h in detail.history],
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        can_edit=detail.may_edit,
        can_change_priority=detail.may_change_priority,
        can_change_photos=detail.may_change_photos,
        can_change_holds=detail.may_change_holds,
        moves=[
            MoveOut(to_status=m.to_status, reason_required=m.reason_required, photos=m.photos)
            for m in detail.moves
        ],
        attempt=detail.attempt,
        store_address=detail.store_address,
    )
