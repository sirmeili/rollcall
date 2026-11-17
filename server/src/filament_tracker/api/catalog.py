"""The catalog: local copies of the Open Filament Database's Bambu Lab colors and
BambuStudio's color code list.

The sync status and Refresh now are Admin only, since a sync is the server contacting the
internet. Failures are reported here and on the Settings page only.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.auth import Admin, DbSession, Viewer
from filament_tracker.db.catalog_models import SyncResult
from filament_tracker.services.catalog_read import read_catalog
from filament_tracker.services.catalog_sync import CatalogSyncer, SyncBusy

router = APIRouter(tags=["catalog"])


class SimilarColorOut(BaseModel):
    product_id: int
    name: str
    hex: str
    material: str
    delta_e: float
    sealed: int
    open: int
    different_material: bool


class CatalogColorOut(BaseModel):
    uuid: str
    name: str
    hexes: list[str]
    discontinued: bool
    multi_color: bool
    # A multi-color one whose colors blend along the filament, not side by side.
    gradient: bool
    # In-stock products within the cutoff, closest first; empty for a multi-color one.
    similar: list[SimilarColorOut]


class FilamentLineOut(BaseModel):
    uuid: str
    name: str
    material: str
    colors: list[CatalogColorOut]


class CatalogOut(BaseModel):
    lines: list[FilamentLineOut]
    synced: bool
    dataset_version: str | None
    last_success_at: datetime | None
    cutoff: float
    # Syncs have failed for 14 days since the last success.
    out_of_date: bool


class SourceStatusOut(BaseModel):
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_result: SyncResult | None
    last_reason: str | None
    # OFDB's only; always null for BambuStudio's list.
    dataset_version: str | None


class SyncStatusOut(BaseModel):
    # Catalog colors in the copy in use.
    colors: int
    ofdb: SourceStatusOut
    bambustudio: SourceStatusOut


def _syncer(request: Request) -> CatalogSyncer:
    return request.app.state.catalog


@router.get("/catalog", response_model=CatalogOut)
def read(_: Viewer, session: DbSession, request: Request) -> CatalogOut:
    """Every filament line with its catalog colors. Search and filters run in the web app
    over this one answer, which is small (about 300 catalog colors)."""
    store: SettingsStore = request.app.state.settings_store
    catalog = read_catalog(session, store.similarity_cutoff())
    return CatalogOut.model_validate(catalog, from_attributes=True)


@router.get("/catalog/sync", response_model=SyncStatusOut)
def sync_status(_: Admin, request: Request) -> SyncStatusOut:
    return SyncStatusOut.model_validate(_syncer(request).status(), from_attributes=True)


@router.post("/catalog/sync", response_model=SyncStatusOut)
def refresh_now(_: Admin, request: Request) -> SyncStatusOut:
    """Sync now and return the new status. A failed sync is a 200 with the failure in it;
    a sync already running is a 409, and nothing new starts."""
    try:
        return SyncStatusOut.model_validate(_syncer(request).sync(), from_attributes=True)
    except SyncBusy:
        raise HTTPException(status.HTTP_409_CONFLICT, "A catalog sync is already running") from None
