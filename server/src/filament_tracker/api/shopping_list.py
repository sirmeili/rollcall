"""The shopping list: what to buy and why (every role reads it), adding to it by hand, what
is on order, choosing an item's size, and dismissing and bringing back its items (Editors and
Admins), and suggestions (every role suggests; Editors and Admins decide). The print requests
short of each product come from the request-needs reader wired in at start (ADR-0020)."""

from fastapi import APIRouter, HTTPException, Request, status

from filament_tracker.api.shopping_schemas import (
    HandReasonIn,
    HandReasonOut,
    LineOut,
    LowStockReasonOut,
    OnOrderIn,
    OrderedIn,
    ReasonOut,
    RequestReasonOut,
    ShoppingHistoryEntryOut,
    ShoppingListItemOut,
    ShoppingListOut,
    SizeIn,
    SizeOut,
    SuggestedColorOut,
    SuggestionIn,
    SuggestionOut,
)
from filament_tracker.api.views import product_detail
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.auth import DbSession, Editor, Principal, Viewer, problems
from filament_tracker.db.models import Product
from filament_tracker.db.types import utcnow
from filament_tracker.services import shopping_list
from filament_tracker.services.catalog_links import UnknownColor
from filament_tracker.services.shopping_list import (
    HandAdded,
    LowStock,
    NoSuchReason,
    NoSuchSuggestion,
    NotDismissed,
    OpenSuggestion,
    RequestNeedsReader,
    RequestShort,
    ShoppingListItem,
    SuggestionDecided,
)

router = APIRouter(tags=["shopping list"])


def _reason_out(reason: LowStock | RequestShort | HandAdded) -> ReasonOut:
    if isinstance(reason, RequestShort):
        # Named and linked only for people allowed to see the request.
        named = reason.title is not None
        return RequestReasonOut(
            request_id=reason.request_id if named else None,
            title=reason.title,
            short_g=reason.short_g,
        )
    if isinstance(reason, LowStock):
        return LowStockReasonOut(
            spools=reason.spools, sealed=reason.sealed, threshold=reason.threshold
        )
    return HandReasonOut(id=reason.id, spools=reason.spools, by=reason.by, at=reason.at)


def _item_out(item: ShoppingListItem) -> ShoppingListItemOut:
    return ShoppingListItemOut(
        product=product_detail(item.product),
        to_buy=item.to_buy,
        need=item.need,
        on_order=item.on_order,
        reasons=[_reason_out(r) for r in item.reasons],
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


def _suggestion_out(suggestion: OpenSuggestion) -> SuggestionOut:
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


def _read(session: DbSession, request: Request, caller: Principal) -> shopping_list.ShoppingList:
    """The list for the caller, with the request-needs reader wired in at start."""
    needs: RequestNeedsReader = request.app.state.request_needs_reader
    return shopping_list.read(session, caller, needs)


def _list_out(session: DbSession, request: Request, caller: Principal) -> ShoppingListOut:
    store: SettingsStore = request.app.state.settings_store
    listed = _read(session, request, caller)
    # Reading clears the dismissals of products that need nothing any more.
    session.commit()
    return ShoppingListOut(
        suggestions=[_suggestion_out(s) for s in shopping_list.open_suggestions(session)],
        lines=[
            LineOut(name=line.name, to_buy=line.to_buy, items=[_item_out(i) for i in line.items])
            for line in listed.lines
        ],
        not_in_catalog=[_item_out(i) for i in listed.not_in_catalog],
        store_address=store.store_address(),
        dismissed=[_item_out(i) for i in listed.dismissed],
    )


def _product(session: DbSession, product_id: int) -> Product:
    found = session.get(Product, product_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such product")
    return found


@router.get("/shopping-list", response_model=ShoppingListOut)
def read(caller: Viewer, session: DbSession, request: Request) -> ShoppingListOut:
    """Each product to buy, as one item with its reasons and recent history, grouped by the
    filament line of its catalog link, then the products not in the catalog. The grams the
    print requests holding filament are short of it are added up and rounded up to spools
    once, by the item's size; a low-stock product needs threshold - sealed + 1 spools on top;
    spools added by hand add to that. A request is named only for people who may see it. A
    dismissed item is under dismissed while its need is at or below the need it was
    dismissed at."""
    return _list_out(session, request, caller)


@router.post("/shopping-list/hand-reasons", response_model=ShoppingListOut)
def add_by_hand(
    body: HandReasonIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Add spools to a product's item by hand, as a reason of its own. A catalog color with
    no linked product gets a provisional "From the catalog" product, linked to it by hand by
    the caller. Answers the list as it now stands."""
    now = utcnow()
    if body.product_id is not None:
        product = _product(session, body.product_id)
    else:
        try:
            product = shopping_list.product_for_color(
                session, body.catalog_color, caller.user_id, now
            )
        except UnknownColor:
            raise problems({"catalog_color": "No such catalog color."}) from None
    shopping_list.add_by_hand(session, product, body.spools, caller.user_id, now)
    session.commit()
    return _list_out(session, request, caller)


@router.delete("/shopping-list/hand-reasons/{reason_id}", response_model=ShoppingListOut)
def remove_hand_reason(
    reason_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Remove a hand-added reason. Answers the list as it now stands."""
    try:
        shopping_list.remove_hand_reason(session, reason_id, caller.user_id, utcnow())
    except NoSuchReason:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such reason") from None
    session.commit()
    return _list_out(session, request, caller)


@router.post("/shopping-list/items/{product_id}/ordered", response_model=ShoppingListOut)
def ordered(
    product_id: int, body: OrderedIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Add spools just ordered to the product's on order; each spool of it that arrives takes
    one off. Answers the list as it now stands."""
    product = _product(session, product_id)
    shopping_list.ordered(session, product, body.spools, caller.user_id, utcnow())
    session.commit()
    return _list_out(session, request, caller)


@router.post("/shopping-list/items/{product_id}/dismiss", response_model=ShoppingListOut)
def dismiss(
    product_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Dismiss a product's item: hide it until more of it is needed than now, and remove its
    hand-added reasons. Answers the list as it now stands."""
    _product(session, product_id)
    item = _read(session, request, caller).find(product_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not on the shopping list")
    if item.hidden:
        raise HTTPException(status.HTTP_409_CONFLICT, "already dismissed")
    if item.need == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "nothing of it is needed")
    shopping_list.dismiss(session, item, caller.user_id, utcnow())
    session.commit()
    return _list_out(session, request, caller)


@router.put("/shopping-list/items/{product_id}/on-order", response_model=ShoppingListOut)
def set_on_order(
    product_id: int, body: OnOrderIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Set the product's on order to any number, to fix a typo or a cancelled order. Answers
    the list as it now stands."""
    product = _product(session, product_id)
    shopping_list.set_on_order(session, product, body.on_order, caller.user_id, utcnow())
    session.commit()
    return _list_out(session, request, caller)


@router.post("/shopping-list/items/{product_id}/bring-back", response_model=ShoppingListOut)
def bring_back(
    product_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Bring back a dismissed item: clear its dismissal, so it shows whatever its need.
    Answers the list as it now stands."""
    _product(session, product_id)
    try:
        shopping_list.bring_back(session, product_id, caller.user_id, utcnow())
    except NotDismissed:
        raise HTTPException(status.HTTP_409_CONFLICT, "not dismissed") from None
    session.commit()
    return _list_out(session, request, caller)


@router.put("/shopping-list/items/{product_id}/size", response_model=ShoppingListOut)
def set_size(
    product_id: int, body: SizeIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Choose the size the product's item turns its requests' grams into spools with. It
    re-rounds only the requests' part. Answers the list as it now stands."""
    product = _product(session, product_id)
    shopping_list.set_size(session, product, body.size_g, caller.user_id, utcnow())
    session.commit()
    return _list_out(session, request, caller)


@router.post("/shopping-list/suggestions", response_model=ShoppingListOut)
def suggest(
    body: SuggestionIn, caller: Viewer, session: DbSession, request: Request
) -> ShoppingListOut:
    """Suggest spools of a product or a catalog color. It counts toward nothing until an
    Editor or Admin adds it; a catalog color already linked to a product suggests that
    product. Answers the list as it now stands."""
    product = _product(session, body.product_id) if body.product_id is not None else None
    try:
        shopping_list.suggest(
            session, product, body.catalog_color, body.spools, caller.user_id, utcnow()
        )
    except UnknownColor:
        raise problems({"catalog_color": "No such catalog color."}) from None
    session.commit()
    return _list_out(session, request, caller)


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
            status.HTTP_409_CONFLICT, "That suggestion was already decided."
        ) from None
    except UnknownColor:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That catalog color is no longer in the catalog."
        ) from None
    session.commit()
    return _list_out(session, request, caller)


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
            status.HTTP_409_CONFLICT, "That suggestion was already decided."
        ) from None
    session.commit()
    return _list_out(session, request, caller)
