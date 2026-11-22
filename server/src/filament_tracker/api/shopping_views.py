"""Turning the shopping list into the API's answer, shared by the shopping list and suggestion
routes. The print requests short of each product come from the request-needs reader wired in
at start (ADR-0020)."""

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from filament_tracker.api.shopping_schemas import (
    HandReasonOut,
    LineOut,
    LowStockReasonOut,
    ReasonOut,
    RequestReasonOut,
    ShoppingHistoryEntryOut,
    ShoppingListItemOut,
    ShoppingListOut,
    SizeOut,
    SuggestedColorOut,
    SuggestionOut,
)
from filament_tracker.api.views import product_detail
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.auth import Principal
from filament_tracker.db.models import Product
from filament_tracker.services import shopping_list
from filament_tracker.services.shopping_list import (
    HandAdded,
    LowStock,
    OpenSuggestion,
    Reason,
    RequestNeedsReader,
    RequestShort,
    ShoppingListItem,
)


def reason_out(reason: Reason) -> ReasonOut:
    match reason:
        case RequestShort():
            # Named and linked only for people allowed to see the request.
            named = reason.title is not None
            return RequestReasonOut(
                request_id=reason.request_id if named else None,
                title=reason.title,
                short_g=reason.short_g,
            )
        case LowStock():
            return LowStockReasonOut(
                spools=reason.spools, sealed=reason.sealed, threshold=reason.threshold
            )
        case HandAdded():
            return HandReasonOut(id=reason.id, spools=reason.spools, by=reason.by, at=reason.at)


def item_out(item: ShoppingListItem) -> ShoppingListItemOut:
    return ShoppingListItemOut(
        product=product_detail(item.product),
        to_buy=item.to_buy,
        need=item.need,
        on_order=item.on_order,
        reasons=[reason_out(r) for r in item.reasons],
        size=SizeOut(grams=item.size.grams, source=item.size.source),
        shopping_history=[
            ShoppingHistoryEntryOut(
                action=e.action,
                spools=e.spools,
                size_g=e.size_g,
                on_order=e.on_order,
                by=e.by,
                at=e.at,
            )
            for e in item.shopping_history
        ],
        dismissed_need=item.dismissed_need,
        new_since_dismissal=item.new_since_dismissal,
    )


def suggestion_out(suggestion: OpenSuggestion) -> SuggestionOut:
    color = suggestion.color
    return SuggestionOut(
        id=suggestion.id,
        product=product_detail(suggestion.product) if suggestion.product else None,
        catalog_color=SuggestedColorOut(
            uuid=suggestion.catalog_uuid,
            name=color.name if color else None,
            line=color.line if color else None,
            hexes=color.hexes if color else None,
            bambu_code=color.bambu_code if color else None,
        )
        if suggestion.catalog_uuid
        else None,
        spools=suggestion.spools,
        by=suggestion.by,
        at=suggestion.at,
    )


def read_list(session: Session, request: Request, caller: Principal) -> shopping_list.ShoppingList:
    """The list for the caller, with the request-needs reader wired in at start."""
    needs: RequestNeedsReader = request.app.state.request_needs_reader
    return shopping_list.read(session, caller, needs)


def list_out(session: Session, request: Request, caller: Principal) -> ShoppingListOut:
    """The list as it now stands, as every shopping list route answers it."""
    store: SettingsStore = request.app.state.settings_store
    listed = read_list(session, request, caller)
    # Reading clears the dismissals of products that need nothing any more.
    session.commit()
    return ShoppingListOut(
        suggestions=[suggestion_out(s) for s in shopping_list.open_suggestions(session)],
        lines=[
            LineOut(name=line.name, to_buy=line.to_buy, items=[item_out(i) for i in line.items])
            for line in listed.lines
        ],
        not_in_catalog=[item_out(i) for i in listed.not_in_catalog],
        store_address=store.store_address(),
        dismissed=[item_out(i) for i in listed.dismissed],
    )


def find_product(session: Session, product_id: int) -> Product:
    """The product, or 404."""
    found = session.get(Product, product_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such product")
    return found
