"""A spool's held grams for Spool detail, and the requests holding it.

Holds name their holder only by type and ID, and Inventory never imports Print Requests
(ADR-0014). So the app wires in a `HolderReader` at start (`print_requests/holders.py`) that
says which request each holder belongs to (ADR-0020). Only Editors and Admins see those
requests.
"""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from filament_tracker.api.read_schemas import HoldingRequestOut, SpoolHeld
from filament_tracker.auth import Principal
from filament_tracker.db.models import Spool
from filament_tracker.domain.enums import Role
from filament_tracker.services import holds
from filament_tracker.services.holds import Holder


@dataclass(frozen=True)
class HoldingRequest:
    id: int
    title: str
    printing: bool


class HolderReader(Protocol):
    def __call__(
        self, session: Session, holders: Collection[Holder]
    ) -> dict[Holder, HoldingRequest]: ...


def holder_reader(request: Request) -> HolderReader:
    return request.app.state.holder_reader


Holding = Annotated[HolderReader, Depends(holder_reader)]


def sees_holders(principal: Principal) -> bool:
    role = principal.role
    return principal.device is None and role is not None and role.allows(Role.EDITOR)


def spool_held(
    session: Session, spool: Spool, reader: HolderReader, principal: Principal
) -> SpoolHeld:
    """Held and available grams. Holds of a Printing request don't count toward over-held."""
    holders = holds.holders_on(session, spool)
    found = reader(session, list(holders))
    printing = {holder for holder, request in found.items() if request.printing}
    grams = holds.spool_grams(session, spool, ignore=printing)
    requests = None
    if sees_holders(principal):
        # A request with two choices on one spool is listed once, by its first hold.
        named = {r.id: r for r in (found.get(h) for h in holders) if r is not None}
        requests = [HoldingRequestOut(id=r.id, title=r.title) for r in named.values()]
    return SpoolHeld(
        held_g=grams.held,
        available_g=grams.available,
        over_held=grams.over_held,
        holding_requests=requests,
    )
