"""Print Requests' answer to Spool detail's question: which requests hold this spool.

Wired in at start as the app's `HolderReader` (`api/spool_holders.py`), so Inventory reads
it without importing Print Requests (ADR-0014, ADR-0020).
"""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.api.spool_holders import HoldingRequest
from filament_tracker.db.request_models import FilamentChoice
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament
from filament_tracker.services.holds import Holder


def holding_requests(session: Session, holders: Collection[Holder]) -> dict[Holder, HoldingRequest]:
    """The request each filament choice holder belongs to; other holders are left out."""
    ids = [h.id for h in holders if h.type == filament.HOLDER_TYPE]
    if not ids:
        return {}
    choices = session.scalars(select(FilamentChoice).where(FilamentChoice.id.in_(ids)))
    return {
        filament.holder(choice): HoldingRequest(
            id=choice.request.id,
            title=choice.request.title,
            printing=choice.request.status is RequestStatus.PRINTING,
        )
        for choice in choices
    }
