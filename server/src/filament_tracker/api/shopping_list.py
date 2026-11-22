"""The shopping list: what to buy and why (every role reads it), adding to it by hand, what
is on order, choosing an item's size, and dismissing and bringing back its items (Editors and
Admins). Suggestions have their own routes (shopping_suggestions)."""

from fastapi import APIRouter, HTTPException, Request, status

from filament_tracker.api.shopping_schemas import (
    HandReasonIn,
    OnOrderIn,
    OrderedIn,
    ShoppingListOut,
    SizeIn,
)
from filament_tracker.api.shopping_views import find_product, list_out, read_list
from filament_tracker.auth import DbSession, Editor, Viewer, problems
from filament_tracker.db.types import utcnow
from filament_tracker.services import shopping_list
from filament_tracker.services.catalog_links import UnknownColor
from filament_tracker.services.shopping_list import NoSuchReason, NotDismissed

router = APIRouter(tags=["shopping list"])


@router.get("/shopping-list", response_model=ShoppingListOut)
def read(caller: Viewer, session: DbSession, request: Request) -> ShoppingListOut:
    """Each product to buy, as one item with its reasons and recent history, grouped by the
    filament line of its catalog link, then the products not in the catalog. The grams the
    print requests holding filament are short of it are added up and rounded up to spools
    once, by the item's size; a low-stock product needs threshold - sealed + 1 spools on top;
    spools added by hand add to that. A request is named only for people who may see it. A
    dismissed item is under dismissed while its need is at or below the need it was
    dismissed at."""
    return list_out(session, request, caller)


@router.post("/shopping-list/hand-reasons", response_model=ShoppingListOut)
def add_by_hand(
    body: HandReasonIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Add spools to a product's item by hand, as a reason of its own. A catalog color with
    no linked product gets a provisional "From the catalog" product, linked to it by hand by
    the caller. Answers the list as it now stands."""
    now = utcnow()
    if body.product_id is not None:
        product = find_product(session, body.product_id)
    else:
        try:
            product = shopping_list.product_for_color(
                session, body.catalog_color, caller.user_id, now
            )
        except UnknownColor:
            raise problems({"catalog_color": "No such catalog color."}) from None
    shopping_list.add_by_hand(session, product, body.spools, caller.user_id, now)
    session.commit()
    return list_out(session, request, caller)


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
    return list_out(session, request, caller)


@router.post("/shopping-list/items/{product_id}/ordered", response_model=ShoppingListOut)
def ordered(
    product_id: int, body: OrderedIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Add spools just ordered to the product's on order; each spool of it that arrives takes
    one off. Answers the list as it now stands."""
    product = find_product(session, product_id)
    shopping_list.ordered(session, product, body.spools, caller.user_id, utcnow())
    session.commit()
    return list_out(session, request, caller)


@router.post("/shopping-list/items/{product_id}/dismiss", response_model=ShoppingListOut)
def dismiss(
    product_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Dismiss a product's item: hide it until more of it is needed than now, and remove its
    hand-added reasons. Answers the list as it now stands."""
    find_product(session, product_id)
    item = read_list(session, request, caller).find(product_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not on the shopping list")
    if item.hidden:
        raise HTTPException(status.HTTP_409_CONFLICT, "already dismissed")
    if item.need == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "nothing of it is needed")
    shopping_list.dismiss(session, item, caller.user_id, utcnow())
    session.commit()
    return list_out(session, request, caller)


@router.put("/shopping-list/items/{product_id}/on-order", response_model=ShoppingListOut)
def set_on_order(
    product_id: int, body: OnOrderIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Set the product's on order to any number, to fix a typo or a cancelled order. Answers
    the list as it now stands."""
    product = find_product(session, product_id)
    shopping_list.set_on_order(session, product, body.on_order, caller.user_id, utcnow())
    session.commit()
    return list_out(session, request, caller)


@router.post("/shopping-list/items/{product_id}/bring-back", response_model=ShoppingListOut)
def bring_back(
    product_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Bring back a dismissed item: clear its dismissal, so it shows whatever its need.
    Answers the list as it now stands."""
    find_product(session, product_id)
    try:
        shopping_list.bring_back(session, product_id, caller.user_id, utcnow())
    except NotDismissed:
        raise HTTPException(status.HTTP_409_CONFLICT, "not dismissed") from None
    session.commit()
    return list_out(session, request, caller)


@router.put("/shopping-list/items/{product_id}/size", response_model=ShoppingListOut)
def set_size(
    product_id: int, body: SizeIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Choose the size the product's item turns its requests' grams into spools with. It
    re-rounds only the requests' part. Answers the list as it now stands."""
    product = find_product(session, product_id)
    shopping_list.set_size(session, product, body.size_g, caller.user_id, utcnow())
    session.commit()
    return list_out(session, request, caller)
