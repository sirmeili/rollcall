"""Read the catalog: its filament lines, each with its catalog colors, in OFDB's order."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import CatalogFilament, CatalogVariant
from filament_tracker.services.catalog_sync import last_success


@dataclass(frozen=True)
class CatalogColor:
    uuid: str
    name: str
    # RRGGBB, the main color first; more than one for a multi-color catalog color.
    hexes: list[str]
    discontinued: bool

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


def read_catalog(session: Session) -> Catalog:
    colors: dict[str, list[CatalogColor]] = {}
    for variant in session.scalars(select(CatalogVariant).order_by(CatalogVariant.position)):
        colors.setdefault(variant.filament_uuid, []).append(
            CatalogColor(
                uuid=variant.uuid,
                name=variant.name,
                hexes=[variant.color_hex, *variant.extra_hexes],
                discontinued=variant.discontinued,
            )
        )
    lines = [
        FilamentLine(line.uuid, line.name, line.material, colors.get(line.uuid, []))
        for line in session.scalars(select(CatalogFilament).order_by(CatalogFilament.position))
    ]
    success = last_success(session)
    return Catalog(
        lines=lines,
        synced=success is not None,
        dataset_version=success.dataset_version if success else None,
        last_success_at=success.finished_at if success else None,
    )
