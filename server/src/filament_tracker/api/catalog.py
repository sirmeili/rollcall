"""The catalog: a local copy of the Open Filament Database's Bambu Lab colors.

The sync status and Refresh now are Admin only, since a sync is the server contacting the
internet. Failures are reported here and on the Settings page only.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from filament_tracker.auth import Admin
from filament_tracker.db.catalog_models import SyncResult
from filament_tracker.services.catalog_sync import CatalogSyncer, SyncBusy, SyncStatus

router = APIRouter(tags=["catalog"])


class SyncStatusOut(BaseModel):
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_result: SyncResult | None
    last_reason: str | None
    dataset_version: str | None
    colors: int


def _out(current: SyncStatus) -> SyncStatusOut:
    return SyncStatusOut(
        last_success_at=current.last_success_at,
        last_attempt_at=current.last_attempt_at,
        last_result=current.last_result,
        last_reason=current.last_reason,
        dataset_version=current.dataset_version,
        colors=current.colors,
    )


def _syncer(request: Request) -> CatalogSyncer:
    return request.app.state.catalog


@router.get("/catalog/sync", response_model=SyncStatusOut)
def sync_status(_: Admin, request: Request) -> SyncStatusOut:
    return _out(_syncer(request).status())


@router.post("/catalog/sync", response_model=SyncStatusOut)
def refresh_now(_: Admin, request: Request) -> SyncStatusOut:
    """Sync now and return the new status. A failed sync is a 200 with the failure in it;
    a sync already running is a 409, and nothing new starts."""
    try:
        return _out(_syncer(request).sync())
    except SyncBusy:
        raise HTTPException(status.HTTP_409_CONFLICT, "A catalog sync is already running") from None
