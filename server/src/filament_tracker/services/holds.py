"""Holds: grams of a spool set aside for a holder, so the same grams are never promised twice.

This is the one place holds are placed and read. A holder is named only by its type and ID
(ADR-0014): Inventory never knows what holds a spool.

- A spool's grams count only while it is Sealed or Open; an Empty or Unknown spool has none.
- Available grams are grams left less active holds, never below 0, and unknown when grams
  left is unknown and nothing is held. A spool is over-held when its holds exceed its grams
  left; the caller names holders that don't count toward that.
- Placing holds for a product takes Open spools with known grams first, least grams left
  first, then Sealed ones, least first. It splits across spools and keeps a partial cover.
- A holder's shortfall is its target less its active held grams, where its grams on a spool
  count only up to that spool's grams left.

Callers own the transaction: nothing here commits.
"""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Spool, SpoolHold
from filament_tracker.domain.enums import SpoolState

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


@dataclass(frozen=True)
class ProductGrams:
    """A product's grams not held, and whether an Open spool's grams are unknown (they are
    left out of `available`)."""

    available: int
    unknown: bool


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


def product_grams(session: Session, product_ids: Collection[int]) -> dict[int, ProductGrams]:
    """Each product's available grams over its Sealed and Open spools, in two queries."""
    query = select(Spool).where(Spool.product_id.in_(product_ids), Spool.state.in_(IN_STOCK))
    spools = list(session.scalars(query))
    held = _held_on(session, [s.id for s in spools])
    available: dict[int, int] = dict.fromkeys(product_ids, 0)
    unknown: set[int] = set()
    for spool in spools:
        available[spool.product_id] += _available(spool, held.get(spool.id, 0)) or 0
        if spool.state is SpoolState.OPEN and spool.grams_left_g is None:
            unknown.add(spool.product_id)
    return {i: ProductGrams(available[i], i in unknown) for i in product_ids}


@dataclass(frozen=True)
class SpoolGrams:
    """A spool's active held grams, its available grams (None when unknown), and whether
    its holds, less any ignored, exceed its grams left."""

    held: int
    available: int | None
    over_held: bool


def holders_on(session: Session, spool: Spool) -> dict[Holder, int]:
    """Each holder's active held grams on the spool, by first hold."""
    query = (
        select(SpoolHold)
        .where(SpoolHold.spool_id == spool.id, SpoolHold.released_at.is_(None))
        .order_by(SpoolHold.id)
    )
    found: dict[Holder, int] = defaultdict(int)
    for hold in session.scalars(query):
        found[Holder(hold.holder_type, hold.holder_id)] += hold.grams
    return dict(found)


def spool_grams(session: Session, spool: Spool, ignore: Collection[Holder] = ()) -> SpoolGrams:
    """The spool's held and available grams. Holders in `ignore` still hold grams but don't
    count toward over-held (the caller decides which: Inventory doesn't know what they are)."""
    holders = holders_on(session, spool)
    held = sum(holders.values())
    left = _grams_left(spool)
    counted = sum(grams for holder, grams in holders.items() if holder not in ignore)
    return SpoolGrams(
        held=held,
        available=_available(spool, held),
        over_held=left is not None and counted > left,
    )


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
    wanted = grams
    for spool, available in candidates:
        if wanted == 0:
            break
        take = min(available, wanted)
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
