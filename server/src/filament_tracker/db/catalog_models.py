"""The catalog's tables: a local copy of the Open Filament Database's (OFDB's) Bambu Lab
colors, BambuStudio's color code list, and a record of each sync of each source.

Rows are keyed by OFDB's own UUIDs, which survive renames, and keep `moved_from` (the UUIDs
a record had before OFDB merged or moved it), so links made to them later still resolve.
A successful sync of a source replaces every row of that source; nothing here refers to
products, spools, tags or events. Products refer to catalog colors by UUID (ADR-0016).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from filament_tracker.db.models import Base
from filament_tracker.db.types import str_enum

UUID_LENGTH = 36
# The longest ETag and Last-Modified headers kept for asking whether the export changed.
ETAG_LENGTH = 200
LAST_MODIFIED_LENGTH = 64


class CatalogBrand(Base):
    __tablename__ = "catalog_brand"

    uuid: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    moved_from: Mapped[list[str]] = mapped_column(JSON, default=list)


class CatalogFilament(Base):
    """A filament line, such as PLA Basic."""

    __tablename__ = "catalog_filament"

    uuid: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True)
    brand_uuid: Mapped[str] = mapped_column(ForeignKey("catalog_brand.uuid"), index=True)
    # The order OFDB lists it in.
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    material: Mapped[str] = mapped_column(String(64))
    density: Mapped[float | None] = mapped_column(Float)
    min_print_temperature: Mapped[int | None] = mapped_column(Integer)
    max_print_temperature: Mapped[int | None] = mapped_column(Integer)
    min_bed_temperature: Mapped[int | None] = mapped_column(Integer)
    max_bed_temperature: Mapped[int | None] = mapped_column(Integer)
    moved_from: Mapped[list[str]] = mapped_column(JSON, default=list)


class CatalogVariant(Base):
    """A catalog color: one color of a filament line. Hexes are RRGGBB, without the #."""

    __tablename__ = "catalog_variant"

    uuid: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True)
    filament_uuid: Mapped[str] = mapped_column(ForeignKey("catalog_filament.uuid"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    color_hex: Mapped[str] = mapped_column(String(6))
    # The other colors of a multi-color catalog color, in OFDB's order.
    extra_hexes: Mapped[list[str]] = mapped_column(JSON, default=list)
    # A multi-color catalog color whose colors blend along the filament (OFDB's
    # gradual_color_change), not side by side in one strand (coextruded).
    gradient: Mapped[bool] = mapped_column(Boolean, default=False)
    discontinued: Mapped[bool] = mapped_column(Boolean, default=False)
    moved_from: Mapped[list[str]] = mapped_column(JSON, default=list)


class CatalogSize(Base):
    """One way a catalog color is sold: a weight, as a refill or on a spool."""

    __tablename__ = "catalog_size"

    uuid: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True)
    variant_uuid: Mapped[str] = mapped_column(ForeignKey("catalog_variant.uuid"), index=True)
    filament_weight: Mapped[float] = mapped_column(Float)
    refill: Mapped[bool] = mapped_column(Boolean, default=False)
    article_number: Mapped[str | None] = mapped_column(String(64))
    discontinued: Mapped[bool] = mapped_column(Boolean, default=False)
    # [{"store": name or null, "url": url}], in OFDB's order.
    purchase_links: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, default=list)
    moved_from: Mapped[list[str]] = mapped_column(JSON, default=list)


class BambuColorCode(Base):
    """One entry of BambuStudio's color code list: the Bambu code a tag's IDs are sold under.
    A tag reads material ID `filament_id` and variant ID `filament_id` without its `GF`
    prefix, a hyphen and `color_code` (GFA00 and K0 give A00-K0)."""

    __tablename__ = "bambu_color_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    bambu_code: Mapped[str] = mapped_column(String(16))
    filament_id: Mapped[str] = mapped_column(String(16))
    # BambuStudio's two-letter code, such as K0. Never shown.
    color_code: Mapped[str] = mapped_column(String(16))


class CatalogSource(StrEnum):
    OFDB = "ofdb"  # the Open Filament Database's export
    BAMBUSTUDIO = "bambustudio"  # BambuStudio's color code list


class SyncResult(StrEnum):
    UPDATED = "updated"  # a new export was downloaded and stored
    NOT_MODIFIED = "not_modified"  # the source said nothing changed (304)
    FAILED = "failed"  # the catalog was left as it was


class CatalogSync(Base):
    """One sync attempt of one source. `etag` and `last_modified` are what the source sent
    with the copy in use, so the next sync can ask whether it changed."""

    __tablename__ = "catalog_sync"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[CatalogSource] = mapped_column(
        str_enum(CatalogSource, "catalog_source"), server_default=CatalogSource.OFDB.value
    )
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime]
    result: Mapped[SyncResult] = mapped_column(str_enum(SyncResult, "sync_result"))
    # Why it failed, in a few words; never the source's answer itself.
    reason: Mapped[str | None] = mapped_column(String(200))
    # OFDB's only.
    dataset_version: Mapped[str | None] = mapped_column(String(64))
    etag: Mapped[str | None] = mapped_column(String(ETAG_LENGTH))
    last_modified: Mapped[str | None] = mapped_column(String(LAST_MODIFIED_LENGTH))
