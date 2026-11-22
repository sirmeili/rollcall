"""The shopping list as the web app reads it, and the changes Editors and Admins make."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from filament_tracker.api.read_schemas import ProductDetail
from filament_tracker.api.schemas import Strict
from filament_tracker.domain.enums import ShoppingAction

# More than anyone would buy at once; it only stops absurd input.
MAX_SPOOLS = 999


class LowStockReasonOut(BaseModel):
    kind: Literal["low_stock"] = "low_stock"
    spools: int = Field(description="Enough spools to stop being low: threshold - sealed + 1")
    sealed: int
    threshold: int


class HandReasonOut(BaseModel):
    kind: Literal["hand"] = "hand"
    id: int
    spools: int
    by: str | None = Field(description="Who added them; null for a token")
    at: datetime


ReasonOut = Annotated[LowStockReasonOut | HandReasonOut, Field(discriminator="kind")]


class HistoryEntryOut(BaseModel):
    action: ShoppingAction
    spools: int | None = Field(description="The spools the action concerned, if any")
    size_g: int | None = Field(description="The size in grams it concerned, if any")
    on_order: int = Field(description="The item's on order once it was done")
    by: str | None = Field(description="Who did it; null for a token")
    at: datetime


class ShoppingListItemOut(BaseModel):
    product: ProductDetail
    to_buy: int = Field(description="need - on order, never below 0")
    need: int = Field(description="The spools its reasons add up to")
    on_order: int = Field(description="Spools ordered and not yet arrived")
    reasons: list[ReasonOut] = Field(description="Low stock first, then hand-added, oldest first")
    history: list[HistoryEntryOut] = Field(description="The most recent entries, newest first")


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


class HandReasonIn(Strict):
    """Spools to add by hand to exactly one of a product or a catalog color (its OFDB UUID).
    A catalog color with no linked product gets a "From the catalog" one."""

    product_id: int | None = None
    catalog_color: Annotated[str, StringConstraints(max_length=36)] | None = None
    spools: int = Field(ge=1, le=MAX_SPOOLS)

    @model_validator(mode="after")
    def one_of(self) -> Self:
        if (self.product_id is None) == (self.catalog_color is None):
            raise ValueError("give a product_id or a catalog_color, not both")
        return self


class OrderedIn(Strict):
    """Spools just ordered, added to the item's on order."""

    spools: int = Field(ge=1, le=MAX_SPOOLS)


class OnOrderIn(Strict):
    """The item's on order, set by hand to fix a typo or a cancelled order."""

    on_order: int = Field(ge=0, le=MAX_SPOOLS)
