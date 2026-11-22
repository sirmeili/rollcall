"""The shopping list: what to buy and why (every role reads it), and adding to it by hand
(Editors and Admins)."""

from fastapi import APIRouter, HTTPException, Request, status

from filament_tracker.api.shopping_schemas import (
    HandReasonIn,
    HandReasonOut,
    HistoryEntryOut,
    LineOut,
    LowStockReasonOut,
    ReasonOut,
    ShoppingListItemOut,
    ShoppingListOut,
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
    ShoppingListItem,
)

router = APIRouter(tags=["shopping list"])


def _reason_out(reason: LowStock | HandAdded) -> ReasonOut:
    if isinstance(reason, LowStock):
        return LowStockReasonOut(
            spools=reason.spools, sealed=reason.sealed, threshold=reason.threshold
        )
    return HandReasonOut(id=reason.id, spools=reason.spools, by=reason.by, at=reason.at)


def _item_out(item: ShoppingListItem) -> ShoppingListItemOut:
    return ShoppingListItemOut(
        product=product_detail(item.product),
        to_buy=item.to_buy,
        reasons=[_reason_out(r) for r in item.reasons],
        history=[
            HistoryEntryOut(
                action=e.action,
                spools=e.spools,
                size_g=e.size_g,
                on_order=e.on_order,
                by=e.by,
                at=e.at,
            )
            for e in item.history
        ],
    )


def _list_out(session: DbSession, request: Request) -> ShoppingListOut:
    store: SettingsStore = request.app.state.settings_store
    listed = shopping_list.read(session)
    return ShoppingListOut(
        lines=[
            LineOut(name=line.name, to_buy=line.to_buy, items=[_item_out(i) for i in line.items])
            for line in listed.lines
        ],
        not_in_catalog=[_item_out(i) for i in listed.not_in_catalog],
        store_address=store.store_address(),
    )


def _user_id(caller: Principal) -> int | None:
    return caller.user.id if caller.user else None


@router.get("/shopping-list", response_model=ShoppingListOut)
def read(_: Viewer, session: DbSession, request: Request) -> ShoppingListOut:
    """Each product to buy, as one item with its reasons and recent history, grouped by the
    filament line of its catalog link, then the products not in the catalog. A low-stock
    product needs threshold - sealed + 1 spools; spools added by hand add to that."""
    return _list_out(session, request)


@router.post("/shopping-list/hand-reasons", response_model=ShoppingListOut)
def add_by_hand(
    body: HandReasonIn, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Add spools to a product's item by hand, as a reason of its own. A catalog color with
    no linked product gets a provisional "From the catalog" product, linked to it by hand by
    the caller. Answers the list as it now stands."""
    now = utcnow()
    if body.catalog_color is not None:
        try:
            product = shopping_list.product_for_color(
                session, body.catalog_color, _user_id(caller), now
            )
        except UnknownColor:
            raise problems({"catalog_color": "No such catalog color."}) from None
    else:
        found = session.get(Product, body.product_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such product")
        product = found
    shopping_list.add_by_hand(session, product, body.spools, _user_id(caller), now)
    session.commit()
    return _list_out(session, request)


@router.delete("/shopping-list/hand-reasons/{reason_id}", response_model=ShoppingListOut)
def remove_hand_reason(
    reason_id: int, caller: Editor, session: DbSession, request: Request
) -> ShoppingListOut:
    """Remove a hand-added reason. Answers the list as it now stands."""
    try:
        shopping_list.remove_hand_reason(session, reason_id, _user_id(caller), utcnow())
    except NoSuchReason:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such reason") from None
    session.commit()
    return _list_out(session, request)
