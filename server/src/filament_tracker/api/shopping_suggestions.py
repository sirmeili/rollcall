"""Suggestions on the shopping list: every role suggests spools of a product or a catalog
color, and Editors and Admins add or dismiss them."""

from fastapi import APIRouter, HTTPException, Request, status

from filament_tracker.api.shopping_schemas import ShoppingListOut, SuggestionIn
from filament_tracker.api.shopping_views import find_product, list_out
from filament_tracker.auth import DbSession, Editor, Viewer, problems
from filament_tracker.db.types import utcnow
from filament_tracker.services import shopping_list
from filament_tracker.services.catalog_links import UnknownColor
from filament_tracker.services.shopping_list import NoSuchSuggestion, SuggestionDecided

router = APIRouter(tags=["shopping list"])


@router.post("/shopping-list/suggestions", response_model=ShoppingListOut)
def suggest(
    body: SuggestionIn, caller: Viewer, session: DbSession, request: Request
) -> ShoppingListOut:
    """Suggest spools of a product or a catalog color. It counts toward nothing until an
    Editor or Admin adds it; a catalog color already linked to a product suggests that
    product. Answers the list as it now stands."""
    product = find_product(session, body.product_id) if body.product_id is not None else None
    try:
        shopping_list.suggest(
            session, product, body.catalog_color, body.spools, caller.user_id, utcnow()
        )
    except UnknownColor:
        raise problems({"catalog_color": "No such catalog color."}) from None
    session.commit()
    return list_out(session, request, caller)


@router.post("/shopping-list/suggestions/{suggestion_id}/add", response_model=ShoppingListOut)
def add_suggestion(
    suggestion_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Add an open suggestion: its spools become a hand-added reason by the caller. A catalog
    color with no linked product gets its "From the catalog" product only now. Answers the
    list as it now stands."""
    try:
        shopping_list.add_suggestion(session, suggestion_id, caller.user_id, utcnow())
    except NoSuchSuggestion:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such suggestion") from None
    except SuggestionDecided:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "that suggestion was already decided"
        ) from None
    except UnknownColor:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "that catalog color is no longer in the catalog"
        ) from None
    session.commit()
    return list_out(session, request, caller)


@router.post("/shopping-list/suggestions/{suggestion_id}/dismiss", response_model=ShoppingListOut)
def dismiss_suggestion(
    suggestion_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Set an open suggestion aside; it adds nothing. Answers the list as it now stands."""
    try:
        shopping_list.dismiss_suggestion(session, suggestion_id, caller.user_id, utcnow())
    except NoSuchSuggestion:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such suggestion") from None
    except SuggestionDecided:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "that suggestion was already decided"
        ) from None
    session.commit()
    return list_out(session, request, caller)
