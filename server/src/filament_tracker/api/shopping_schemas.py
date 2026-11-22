"""The shopping list as the web app reads it."""

from typing import Literal

from pydantic import BaseModel, Field

from filament_tracker.api.read_schemas import ProductDetail


class LowStockReasonOut(BaseModel):
    kind: Literal["low_stock"] = "low_stock"
    spools: int = Field(description="Enough spools to stop being low: threshold - sealed + 1")
    sealed: int
    threshold: int


class ShoppingListItemOut(BaseModel):
    product: ProductDetail
    to_buy: int
    reasons: list[LowStockReasonOut]


class LineOut(BaseModel):
    name: str = Field(description="The filament line, such as PLA Basic")
    to_buy: int = Field(description="The line's items' to buy, added up")
    items: list[ShoppingListItemOut] = Field(description="By product name")


class ShoppingListOut(BaseModel):
    lines: list[LineOut] = Field(description="By name")
    not_in_catalog: list[ShoppingListItemOut] = Field(
        description="Products with no catalog link, by name"
    )
    store_address: str = Field(description="The store Find in store searches, no trailing slash")
