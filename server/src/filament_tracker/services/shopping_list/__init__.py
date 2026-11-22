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
from filament_tracker.services.shopping_list.read import (
    HandAdded,
    Line,
    LowStock,
    ShoppingList,
    ShoppingListItem,
    read,
)
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
    "HistoryEntry",
    "Line",
    "LowStock",
    "NoSuchReason",
    "NoSuchSuggestion",
    "OpenSuggestion",
    "ShoppingList",
    "ShoppingListItem",
    "SuggestionDecided",
    "add_by_hand",
    "add_suggestion",
    "dismiss_suggestion",
    "open_suggestions",
    "product_for_color",
    "read",
    "remove_hand_reason",
    "suggest",
]
