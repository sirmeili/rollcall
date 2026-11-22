"""Response bodies for the pages of the web app."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Matching items across all pages")
    limit: int
    offset: int


class CatalogLinkOut(BaseModel):
    """A product's catalog link. The color's fields are null when it is no longer in the
    catalog (a manual link to a color OFDB dropped)."""

    uuid: str | None
    name: str | None
    line: str | None = Field(description="The filament line, such as PLA Basic")
    hexes: list[str] | None = Field(description="RRGGBB, the main color first")
    bambu_code: str | None
    how: str = Field(description="tag (automatic) or hand (manual)")
    in_catalog: bool
    linked_by: str | None = Field(description="For a manual link: who set it")
    linked_at: datetime | None = Field(description="For a manual link: when")
    was_line: str | None = Field(description="No longer in the catalog: the line it was in")
    was_name: str | None = Field(description="No longer in the catalog: the color it was")
    tag_link_exists: bool = Field(
        description="The product's tag gives a catalog color, which clearing a manual link "
        "goes back to"
    )


class ProductDetail(BaseModel):
    id: int
    display_name: str
    filament_type: str
    color_rgba: str = Field(description="RRGGBBAA, for the color swatch")
    material_id: str | None
    variant_id: str | None
    low_stock_threshold: int = Field(description="Low on stock at or below this; 0 is off")
    nearly_out_pct: int = Field(description="An open spool at or below this AMS % is nearly out")
    provisional: bool
    from_ams: bool = Field(description="Made from an AMS report rather than by hand")
    from_catalog: bool = Field(
        description="Made from a catalog color put on the shopping list, until a tag fills it in"
    )
    catalog_link: CatalogLinkOut | None = Field(
        default=None, description="Its catalog color; null when it has none"
    )


class Counts(BaseModel):
    sealed: int = 0
    open: int = 0
    empty: int = 0
    unknown: int = 0


class OpenSpool(BaseModel):
    id: int
    remaining_pct: int | None = Field(description="From the AMS; null until it reports one")
    nearly_out: bool = Field(description="Remaining % known and at or below the product's cutoff")


class ProductSummary(BaseModel):
    """A product with its spool counts: one inventory card."""

    product: ProductDetail
    counts: Counts
    low_stock: bool
    open_spools: list[OpenSpool] = Field(description="Open spools, oldest opened first")
    available_g: int = Field(
        description="About how many grams of its Sealed and Open spools are not held, leaving "
        "out spools whose grams are unknown"
    )
    available_unknown: bool = Field(description="An Open spool's grams are unknown")


class AmsSlotRef(BaseModel):
    printer_id: int
    printer_name: str
    ams_index: int = Field(description="0-3: AMS 1 to 4; 128 and up: AMS HT 1, 2...")
    tray_index: int = Field(description="0-based; shown as slot 1 to 4")


class SpoolRow(BaseModel):
    id: int
    state: str = Field(description="sealed, open, empty or unknown")
    product: ProductDetail
    placeholder: bool = Field(description="Added by hand and not yet linked to a tag")
    location: str | None
    remaining_pct: int | None
    net_weight_g: int | None = Field(description="Grams of filament when full")
    grams_left_g: int | None = Field(description="About how many grams are left; null if unknown")
    received_at: datetime | None
    opened_at: datetime | None
    emptied_at: datetime | None
    ams_slot: AmsSlotRef | None = Field(description="Where the spool is loaded, if anywhere")


class TagOut(BaseModel):
    uid: str
    first_seen_at: datetime
    decoded: dict[str, Any] | None = Field(description="Decoded tag fields; null if unreadable")
    decoder_version: int | None


class EventOut(BaseModel):
    id: UUID
    spool_id: int
    product_name: str
    color_rgba: str
    type: str
    source: str
    occurred_at: datetime
    recorded_at: datetime
    flagged: bool
    device_id: str | None
    device_name: str | None
    username: str | None
    reverts: UUID | None = Field(description="For an undo: the event it undid")
    reverted_by: UUID | None
    can_undo: bool
    reviewed_at: datetime | None = Field(description="When a flagged event was accepted")
    reviewed_by: str | None = Field(description="Who accepted it; null for the admin token")


class HoldingRequestOut(BaseModel):
    id: int
    title: str


class SpoolHeld(BaseModel):
    held_g: int = Field(description="Grams held for requests")
    available_g: int | None = Field(
        description="About how many grams are not held, never below 0; null if unknown"
    )
    over_held: bool = Field(
        description="Held beyond its grams left, leaving out holds of Printing requests"
    )
    holding_requests: list[HoldingRequestOut] | None = Field(
        description="The requests holding it; Editors and Admins only, else null"
    )


class SpoolDetail(SpoolRow, SpoolHeld):
    notes: str | None
    tags: list[TagOut]
    events: list[EventOut] = Field(description="Newest first")


class UnidentifiedTag(BaseModel):
    uid: str
    first_seen_at: datetime
    readable: bool = Field(description="False if the tag's blocks could not be decoded")
    decoded: dict[str, Any] | None


class ReviewOut(BaseModel):
    flagged_events: list[EventOut] = Field(description="Flagged and not undone, newest first")
    unidentified_tags: list[UnidentifiedTag]
    likely_empty: list[SpoolRow] = Field(
        description="Open spools the AMS reports at 0%, not dismissed"
    )
