"""The shopping list: one item per product that needs buying, with the reasons it is there.
Each item's need is worked out live every time the list is read; nothing about it is stored
(ADR-0021)."""

from filament_tracker.services.shopping_list.catalog_products import product_for_color
from filament_tracker.services.shopping_list.hand import (
    NoSuchReason,
    add_by_hand,
    remove_hand_reason,
)
from filament_tracker.services.shopping_list.history import HistoryEntry
from filament_tracker.services.shopping_list.needs import RequestNeedsReader, RequestShort
from filament_tracker.services.shopping_list.net_weight import NetWeight, SizeFrom
from filament_tracker.services.shopping_list.on_order import ordered, set_on_order
from filament_tracker.services.shopping_list.read import (
    HandAdded,
    Line,
    LowStock,
    ShoppingList,
    ShoppingListItem,
    read,
)
from filament_tracker.services.shopping_list.size import set_size

__all__ = [
    "HandAdded",
    "HistoryEntry",
    "Line",
    "LowStock",
    "NetWeight",
    "NoSuchReason",
    "RequestNeedsReader",
    "RequestShort",
    "ShoppingList",
    "ShoppingListItem",
    "SizeFrom",
    "add_by_hand",
    "ordered",
    "product_for_color",
    "read",
    "remove_hand_reason",
    "set_on_order",
    "set_size",
]
