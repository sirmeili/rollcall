"""Holds: grams of a spool set aside for a holder, so the same grams are never promised twice.

This is the one place holds are placed and read. A holder is named only by its type and ID
(ADR-0014): Inventory never knows what holds a spool.

- A spool's grams count only while it is Sealed or Open; an Empty or Unknown spool has none.
- Available grams are grams left less active holds, never below 0, and unknown when grams
  left is unknown and nothing is held.
- Placing holds for a product takes Open spools with known grams first, least grams left
  first, then Sealed ones, least first. It splits across spools and keeps a partial cover.
  More for a spool the holder already holds is added to that hold: one hold per spool.
- A holder's shortfall is its target less its active held grams, where its grams on a spool
  count only up to that spool's grams left.
- Releasing a holder's holds keeps them, with when and why they were released; their grams
  are then available again. A spool that becomes Empty or Unknown has its holds released as
  `spool_gone`. A release is a stock change (ADR-0020).

Callers own the transaction: nothing here commits.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Spool, SpoolHold
from filament_tracker.domain.enums import ReleaseReason, SpoolState
from filament_tracker.services import stock_changes

IN_STOCK = (SpoolState.SEALED, SpoolState.OPEN)


@dataclass(frozen=True)
class Holder:
    """What holds grams, by type (such as `filament_choice`) and ID."""

    type: str
    id: int


@dataclass(frozen=True)
class Placed:
    held: int
    short: int


def _grams_left(spool: Spool) -> int | None:
    """A spool's grams left, 0 once it is Empty or Unknown."""
    return spool.grams_left_g if spool.state in IN_STOCK else 0


def _held_on(session: Session, spool_ids: list[int]) -> dict[int, int]:
    """Active held grams on each of these spools."""
    held: dict[int, int] = defaultdict(int)
    query = select(SpoolHold).where(
        SpoolHold.spool_id.in_(spool_ids), SpoolHold.released_at.is_(None)
    )
    for hold in session.scalars(query):
        held[hold.spool_id] += hold.grams
    return held


def _available(spool: Spool, held: int) -> int | None:
    left = _grams_left(spool)
    if left is None:
        return None if held == 0 else 0
    return max(left - held, 0)


def spool_available(session: Session, spool: Spool) -> int | None:
    """The spool's grams not held, or None when unknown."""
    return _available(spool, _held_on(session, [spool.id]).get(spool.id, 0))


def _in_stock(session: Session, product_id: int) -> list[Spool]:
    query = select(Spool).where(Spool.product_id == product_id, Spool.state.in_(IN_STOCK))
    return list(session.scalars(query))


def product_available(session: Session, product_id: int) -> int:
    """The grams not held over the product's Sealed and Open spools, leaving out spools
    whose grams are unknown."""
    spools = _in_stock(session, product_id)
    held = _held_on(session, [s.id for s in spools])
    return sum(_available(s, held.get(s.id, 0)) or 0 for s in spools)


def place(
    session: Session, holder: Holder, product_id: int | None, grams: int, now: datetime
) -> Placed:
    """Hold `grams` of the product for the holder, as much as its spools have (none for no
    product), and say how much was held and how much is short."""
    spools = _in_stock(session, product_id) if product_id is not None else []
    held = _held_on(session, [s.id for s in spools])
    candidates = [
        (spool, available)
        for spool in spools
        if (available := _available(spool, held.get(spool.id, 0)))
    ]
    candidates.sort(key=lambda c: (c[0].state is not SpoolState.OPEN, c[0].grams_left_g, c[0].id))
    own = {hold.spool_id: hold for hold in active_holds(session, holder)}
    wanted = grams
    for spool, available in candidates:
        if wanted == 0:
            break
        take = min(available, wanted)
        if spool.id in own:
            own[spool.id].grams += take
        else:
            session.add(
                SpoolHold(
                    spool_id=spool.id,
                    grams=take,
                    holder_type=holder.type,
                    holder_id=holder.id,
                    created_at=now,
                )
            )
        wanted -= take
    session.flush()
    return Placed(held=grams - wanted, short=wanted)


def active_holds(session: Session, holder: Holder) -> list[SpoolHold]:
    """The holder's holds not yet released, oldest first."""
    query = (
        select(SpoolHold)
        .where(
            SpoolHold.holder_type == holder.type,
            SpoolHold.holder_id == holder.id,
            SpoolHold.released_at.is_(None),
        )
        .order_by(SpoolHold.id)
    )
    return list(session.scalars(query))


def _release(
    session: Session, released: list[SpoolHold], reason: ReleaseReason, now: datetime
) -> list[SpoolHold]:
    for hold in released:
        hold.released_at = now
        hold.release_reason = reason
    session.flush()
    if released:
        stock_changes.changed(session)
    return released


def release(
    session: Session, holder: Holder, reason: ReleaseReason, now: datetime
) -> list[SpoolHold]:
    """Release the holder's active holds, keeping them with the time and reason; the holds
    released, oldest first."""
    return _release(session, active_holds(session, holder), reason, now)


def release_gone(session: Session, spool: Spool, now: datetime) -> list[SpoolHold]:
    """Release the active holds on a spool that is no longer Sealed or Open, as `spool_gone`;
    the holds released, oldest first."""
    if spool.state in IN_STOCK:
        return []
    query = (
        select(SpoolHold)
        .where(SpoolHold.spool_id == spool.id, SpoolHold.released_at.is_(None))
        .order_by(SpoolHold.id)
    )
    return _release(session, list(session.scalars(query)), ReleaseReason.SPOOL_GONE, now)


def shortfall(session: Session, holder: Holder, target: int) -> int:
    """The target grams less what the holder holds, counting each spool only up to its
    grams left; never below 0."""
    by_spool: dict[int, int] = defaultdict(int)
    spools: dict[int, Spool] = {}
    for hold in active_holds(session, holder):
        by_spool[hold.spool_id] += hold.grams
        spools[hold.spool_id] = hold.spool
    counted = sum(min(grams, _grams_left(spools[i]) or 0) for i, grams in by_spool.items())
    return max(target - counted, 0)
