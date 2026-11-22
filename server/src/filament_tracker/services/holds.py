"""Holds: grams of a spool set aside for a holder, so the same grams are never promised twice.

This is the one place holds are placed and read. A holder is named only by its type and ID
(ADR-0014): Inventory never knows what holds a spool.

- A spool's grams count only while it is Sealed or Open; an Empty or Unknown spool has none.
- Available grams are grams left less active holds, never below 0, and unknown when grams
  left is unknown and nothing is held. A spool is over-held when its holds exceed its grams
  left; the caller names holders that don't count toward that.
- Holding by hand takes a given spool of any product.
- Placing holds for a product takes Open spools with known grams first, least grams left
  first, then Sealed ones, least first. It splits across spools and keeps a partial cover.
  More for a spool the holder already holds is added to that hold: one hold per spool.
- How short holders are is worked out in an order the caller gives: each is short its
  target less its active held grams, where a spool's grams left go to its holders in that
  order, each taking up to what it holds there. On an over-held spool the later holders are
  short; a holder not in the order takes none.
- Releasing a holder's holds keeps them, with when and why they were released; their grams
  are then available again. A spool that becomes Empty or Unknown has its holds released as
  `spool_gone`. A release is a stock change (ADR-0020).

Callers own the transaction: nothing here commits.
"""

from collections import defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_, select
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


def _active_on(session: Session, spool: Spool) -> list[SpoolHold]:
    """The spool's holds not yet released, oldest first."""
    query = (
        select(SpoolHold)
        .where(SpoolHold.spool_id == spool.id, SpoolHold.released_at.is_(None))
        .order_by(SpoolHold.id)
    )
    return list(session.scalars(query))


def holders_on(session: Session, spool: Spool) -> dict[Holder, int]:
    """Each holder's active held grams on the spool, by first hold."""
    found: dict[Holder, int] = defaultdict(int)
    for hold in _active_on(session, spool):
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
    own = {hold.spool_id: hold for hold in active_holds(session, holder)}
    wanted = grams
    for spool, available in candidates:
        if wanted == 0:
            break
        take = min(available, wanted)
        _add(session, holder, spool, take, own.get(spool.id), now)
        wanted -= take
    session.flush()
    return Placed(held=grams - wanted, short=wanted)


def _add(
    session: Session,
    holder: Holder,
    spool: Spool,
    grams: int,
    own: SpoolHold | None,
    now: datetime,
) -> None:
    """Add the grams to the holder's hold on the spool, or hold them anew."""
    if own is not None:
        own.grams += grams
        return
    session.add(
        SpoolHold(
            spool_id=spool.id,
            grams=grams,
            holder_type=holder.type,
            holder_id=holder.id,
            created_at=now,
        )
    )


def hold(session: Session, holder: Holder, spool: Spool, grams: int, now: datetime) -> None:
    """Hold `grams` of this spool for the holder by hand, whatever its product: added to the
    holder's hold on the spool if it has one. The caller checks the spool and the grams."""
    own = next((h for h in active_holds(session, holder) if h.spool_id == spool.id), None)
    _add(session, holder, spool, grams, own, now)
    session.flush()


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


def release_hold(session: Session, hold: SpoolHold, reason: ReleaseReason, now: datetime) -> None:
    """Release one active hold, keeping it with the time and reason."""
    _release(session, [hold], reason, now)


def release_gone(session: Session, spool: Spool, now: datetime) -> list[SpoolHold]:
    """Release the active holds on a spool that is no longer Sealed or Open, as `spool_gone`;
    the holds released, oldest first."""
    if spool.state in IN_STOCK:
        return []
    return _release(session, _active_on(session, spool), ReleaseReason.SPOOL_GONE, now)


def _holds_of(session: Session, holders: Collection[Holder]) -> list[SpoolHold]:
    """The active holds of these holders, oldest first."""
    by_type: dict[str, list[int]] = defaultdict(list)
    for holder in holders:
        by_type[holder.type].append(holder.id)
    if not by_type:
        return []
    of_holders = or_(
        *(
            and_(SpoolHold.holder_type == kind, SpoolHold.holder_id.in_(ids))
            for kind, ids in by_type.items()
        )
    )
    query = select(SpoolHold).where(SpoolHold.released_at.is_(None), of_holders)
    return list(session.scalars(query.order_by(SpoolHold.id)))


def short(session: Session, targets: Mapping[Holder, int]) -> dict[Holder, int]:
    """How short each holder is: its target grams less what it holds, never below 0. The
    order of `targets` is the order a spool's grams left go to its holders: each takes up to
    what it holds there, so on an over-held spool the later ones are short. Holders not in
    `targets` take none of them. Unknown grams left count as 0."""
    held: dict[int, dict[Holder, int]] = defaultdict(lambda: defaultdict(int))
    spools: dict[int, Spool] = {}
    for hold in _holds_of(session, targets):
        held[hold.spool_id][Holder(hold.holder_type, hold.holder_id)] += hold.grams
        spools[hold.spool_id] = hold.spool
    counted: dict[Holder, int] = defaultdict(int)
    for spool_id, by_holder in held.items():
        left = _grams_left(spools[spool_id]) or 0
        for holder in targets:
            take = min(by_holder.get(holder, 0), left)
            counted[holder] += take
            left -= take
    return {holder: max(target - counted[holder], 0) for holder, target in targets.items()}
