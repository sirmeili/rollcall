"""The shopping list: what to buy and why (every role reads it)."""

from fastapi import APIRouter, Request

from filament_tracker.api.shopping_schemas import (
    LineOut,
    LowStockReasonOut,
    ShoppingListItemOut,
    ShoppingListOut,
)
from filament_tracker.api.views import product_detail
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.auth import DbSession, Viewer
from filament_tracker.services import shopping_list
from filament_tracker.services.shopping_list import ShoppingListItem

router = APIRouter(tags=["shopping list"])


def _item_out(item: ShoppingListItem) -> ShoppingListItemOut:
    return ShoppingListItemOut(
        product=product_detail(item.product),
        to_buy=item.to_buy,
        reasons=[
            LowStockReasonOut(spools=r.spools, sealed=r.sealed, threshold=r.threshold)
            for r in item.reasons
        ],
    )


@router.get("/shopping-list", response_model=ShoppingListOut)
def read(_: Viewer, session: DbSession, request: Request) -> ShoppingListOut:
    """Each product to buy, as one item with its reasons, grouped by the filament line of its
    catalog link, then the products not in the catalog. A low-stock product needs
    threshold - sealed + 1 spools."""
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
