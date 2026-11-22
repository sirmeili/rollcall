"""The shopping list: one item per product that needs buying, with the reasons it is there.
Each item's need is worked out live every time the list is read; nothing about it is stored
(ADR-0021)."""

from filament_tracker.services.shopping_list.catalog_products import product_for_color
from filament_tracker.services.shopping_list.dismiss import NotDismissed, bring_back, dismiss
from filament_tracker.services.shopping_list.hand import (
    NoSuchReason,
    add_by_hand,
    remove_hand_reason,
)
from filament_tracker.services.shopping_list.needs import RequestNeedsReader, RequestShort
from filament_tracker.services.shopping_list.net_weight import NetWeight, SizeFrom
from filament_tracker.services.shopping_list.on_order import ordered, set_on_order
from filament_tracker.services.shopping_list.read import (
    HandAdded,
    Line,
    LowStock,
    Reason,
    ShoppingList,
    ShoppingListItem,
    read,
)
from filament_tracker.services.shopping_list.shopping_history import ShoppingHistoryEntry
from filament_tracker.services.shopping_list.size import set_size
from filament_tracker.services.shopping_list.stage import ItemStage, Stage, stages
from filament_tracker.services.shopping_list.suggestions import (
    NoSuchSuggestion,
    OpenSuggestion,
    SuggestionDecided,
    add_suggestion,
    dismiss_suggestion,
    open_suggestions,
    suggest,
)

__all__ = [
    "HandAdded",
    "ItemStage",
    "Line",
    "LowStock",
    "NetWeight",
    "NoSuchReason",
    "NoSuchSuggestion",
    "NotDismissed",
    "OpenSuggestion",
    "Reason",
    "RequestNeedsReader",
    "RequestShort",
    "ShoppingList",
    "ShoppingHistoryEntry",
    "ShoppingListItem",
    "SizeFrom",
    "Stage",
    "SuggestionDecided",
    "add_by_hand",
    "add_suggestion",
    "bring_back",
    "dismiss",
    "dismiss_suggestion",
    "open_suggestions",
    "ordered",
    "product_for_color",
    "read",
    "remove_hand_reason",
    "set_on_order",
    "set_size",
    "stages",
    "suggest",
]
