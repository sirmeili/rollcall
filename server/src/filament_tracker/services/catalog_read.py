"""Read the catalog: its filament lines, each with its catalog colors in OFDB's order, and
for each single-color catalog color its similar in-stock colors.

A similar in-stock color is a product with at least one Sealed or Open spool (provisional
products count, with the color they were entered with) whose color is within the cutoff
(CIEDE2000), in any material. They are sorted closest first, the same material first on a
tie. The material is compared exactly, ignoring case and spaces, so PLA-CF is not PLA.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import (
    CatalogFilament,
    CatalogSource,
    CatalogSync,
    CatalogVariant,
    SyncResult,
)
from filament_tracker.db.types import utcnow
from filament_tracker.domain.color import Lab, ciede2000, hex_to_lab
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services.catalog_sync import last_attempt, last_success
from filament_tracker.services.queries import inventory

# Syncs failing for this long since the last success make the catalog out of date.
OUT_OF_DATE_AFTER = timedelta(days=14)


@dataclass(frozen=True)
class SimilarColor:
    product_id: int
    name: str
    # RRGGBB
    hex: str
    material: str
    delta_e: float
    sealed: int
    open: int
    different_material: bool


@dataclass(frozen=True)
class CatalogColor:
    uuid: str
    name: str
    # RRGGBB, the main color first; more than one for a multi-color catalog color.
    hexes: list[str]
    discontinued: bool
    # Its colors blend along the filament rather than sit side by side.
    gradient: bool = False
    similar: list[SimilarColor] = field(default_factory=list)

    @property
    def multi_color(self) -> bool:
        return len(self.hexes) > 1


@dataclass(frozen=True)
class FilamentLine:
    uuid: str
    name: str
    material: str
    colors: list[CatalogColor]


@dataclass(frozen=True)
class Catalog:
    lines: list[FilamentLine]
    # Whether a sync has ever worked, so the catalog has been downloaded.
    synced: bool
    dataset_version: str | None
    last_success_at: datetime | None
    # The ΔE the similar in-stock colors were found with.
    cutoff: float
    # Syncs have failed for 14 days since the last success.
    out_of_date: bool


@dataclass(frozen=True)
class _Stocked:
    product_id: int
    name: str
    hex: str
    material: str
    lab: Lab
    sealed: int
    open: int


def same_material(a: str, b: str) -> bool:
    """PLA and pla match; PLA and PLA-CF don't."""
    return re.sub(r"\s+", "", a).lower() == re.sub(r"\s+", "", b).lower()


def _in_stock(session: Session) -> list[_Stocked]:
    stocked = []
    for item in inventory(session):
        sealed = item.counts.get(SpoolState.SEALED, 0)
        open_ = item.counts.get(SpoolState.OPEN, 0)
        if sealed + open_ == 0:
            continue
        product = item.product
        hex_ = product.color_rgba[:6].upper()
        stocked.append(
            _Stocked(
                product.id,
                product.display_name,
                hex_,
                product.filament_type,
                hex_to_lab(hex_),
                sealed,
                open_,
            )
        )
    return stocked


def _similar(
    hex_: str, material: str, stocked: list[_Stocked], cutoff: float
) -> list[SimilarColor]:
    lab = hex_to_lab(hex_)
    found = []
    for product in stocked:
        delta_e = ciede2000(lab, product.lab)
        if delta_e <= cutoff:
            found.append(
                SimilarColor(
                    product_id=product.product_id,
                    name=product.name,
                    hex=product.hex,
                    material=product.material,
                    delta_e=round(delta_e, 1),
                    sealed=product.sealed,
                    open=product.open,
                    different_material=not same_material(material, product.material),
                )
            )
    return sorted(found, key=lambda m: (m.delta_e, m.different_material, m.name))


def _out_of_date(session: Session, success: CatalogSync | None, now: datetime) -> bool:
    """OFDB's freshness only: a stale BambuStudio list only delays new automatic links."""
    attempt = last_attempt(session, CatalogSource.OFDB)
    if success is None or attempt is None or attempt.result != SyncResult.FAILED:
        return False
    return now - success.finished_at >= OUT_OF_DATE_AFTER


def read_catalog(session: Session, cutoff: float, now: datetime | None = None) -> Catalog:
    stocked = _in_stock(session)
    lines_in_order = list(
        session.scalars(select(CatalogFilament).order_by(CatalogFilament.position))
    )
    materials = {line.uuid: line.material for line in lines_in_order}
    colors: dict[str, list[CatalogColor]] = {}
    for variant in session.scalars(select(CatalogVariant).order_by(CatalogVariant.position)):
        hexes = [variant.color_hex, *variant.extra_hexes]
        # A multi-color catalog color gets no comparison.
        similar = (
            []
            if len(hexes) > 1
            else _similar(variant.color_hex, materials[variant.filament_uuid], stocked, cutoff)
        )
        colors.setdefault(variant.filament_uuid, []).append(
            CatalogColor(
                uuid=variant.uuid,
                name=variant.name,
                hexes=hexes,
                discontinued=variant.discontinued,
                gradient=variant.gradient,
                similar=similar,
            )
        )
    lines = [
        FilamentLine(line.uuid, line.name, line.material, colors.get(line.uuid, []))
        for line in lines_in_order
    ]
    success = last_success(session, CatalogSource.OFDB)
    return Catalog(
        lines=lines,
        synced=success is not None,
        dataset_version=success.dataset_version if success else None,
        last_success_at=success.finished_at if success else None,
        cutoff=cutoff,
        out_of_date=_out_of_date(session, success, now or utcnow()),
    )
