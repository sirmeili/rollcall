"""A request's filament: grams and holds on its filament choices.

Each choice is a holder in Inventory's hold service, as `filament_choice` and its ID. A
product choice is held on that product; a catalog color choice on the product whose
effective catalog link is that color, and with none, all its grams are short. A choice is
covered when it is short 0 g: see `short` for how an over-held spool is shared.

**Approve** takes grams for every choice, from 1 to 100,000, for the whole quantity. In one
transaction it records Approved by the Admin, gives each catalog color choice with no linked
product the shopping list's "From the catalog" product, linked by hand by the Admin, places
holds, and moves on automatically, with no user: to Queued when every choice is covered,
otherwise to Waiting on Filament.

**Reprint** takes grams for every choice in the same way, pre-filled on the page from the
last attempt's. It places holds and lands on Queued when every choice is covered, otherwise
on Waiting on Filament: one move by the Admin either way, with no email.

The moves to Done, Failed and Cancelled release the request's holds, with that reason.

**The retry when stock changes** (ADR-0020): Approved and Waiting on Filament requests are
retried in Active-tab order: each short choice takes more holds, and a request with every
choice covered moves to Queued automatically, with no user and no email. A Queued request is
never moved back; one that becomes short shows its shortfall. An over-held spool's grams left
go to the requests in the same order (`short`).

**Holds by hand**: a signed-in Admin changes a request's holds while it is Approved, Waiting
on Filament or Queued: a choice's grams (holding them again), a hold's spool or grams, a hold
on any Sealed or Open spool (of another product, say, for a similar color), or no hold. A
hold by hand takes no more than the spool has available, unless its grams are unknown. Each
change names the status it expects, releases what it replaces as `changed`, writes one
`holds_changed` entry, sends no email, and checks the request again: it moves to Queued once
covered, but takes no more holds until a later retry, so the change isn't undone. A request
whose holds were changed by hand in this transaction is only checked by the retry its change
sets off; later retries treat it as any other.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Spool, SpoolHold, User
from filament_tracker.db.request_models import FilamentChoice, PrintRequest, RequestHistory
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import HistoryKind, ReleaseReason, RequestStatus
from filament_tracker.print_requests import pipeline
from filament_tracker.print_requests.pipeline import Moved, Mover
from filament_tracker.print_requests.read import sort_key
from filament_tracker.print_requests.refused import Refused
from filament_tracker.services import holds, shopping_list
from filament_tracker.services.catalog_links import UnknownColor, linked_product

HOLDER_TYPE = "filament_choice"
NOT_NOW = "Holds can be changed only while a request is Approved, Waiting on Filament or Queued."

_GRAMS_MIN = 1
_GRAMS_MAX = 100_000
_GRAMS = "grams"
_GRAMS_NEEDED = "Give the grams for this filament."
_GRAMS_RANGE = f"Grams must be {_GRAMS_MIN} to {_GRAMS_MAX:,}."
_NOT_ITS_CHOICES = "Give grams only for its filaments."
_ONLY_ON_APPROVE = "Grams are given only when approving or reprinting."
_SPOOL = "spool_id"
_NOT_ON_THE_SHELF = "Choose a Sealed or Open spool."
_NO_SUCH_CHOICE = "no such filament choice"
_NO_SUCH_HOLD = "no such hold"

# The moves that release a request's holds, and why.
_RELEASES = {
    RequestStatus.DONE: ReleaseReason.DONE,
    RequestStatus.FAILED: ReleaseReason.FAILED,
    RequestStatus.CANCELLED: ReleaseReason.CANCELLED,
}

# Where a request waits for filament, and is retried when stock changes.
_WAITING = (RequestStatus.APPROVED, RequestStatus.WAITING_ON_FILAMENT)

# The session's requests whose holds were changed by hand, which its retry only checks.
_CHANGED_BY_HAND = "holds_changed_by_hand"


def holder(choice: FilamentChoice) -> holds.Holder:
    return holds.Holder(HOLDER_TYPE, choice.id)


def product_id(session: Session, choice: FilamentChoice) -> int | None:
    """The product the choice is held on, if any."""
    if choice.product_id is not None:
        return choice.product_id
    product = linked_product(session, choice.catalog_uuid or "")
    return None if product is None else product.id


def _grams_problem(field: str) -> str:
    """The key a choice's grams problem is reported under: `grams.<choice ID>`."""
    return f"{_GRAMS}.{field}"


def _grams_in_range(grams: int) -> bool:
    """Whether a choice's or a hold's grams are from _GRAMS_MIN to _GRAMS_MAX."""
    return _GRAMS_MIN <= grams <= _GRAMS_MAX


# Approving and reprinting


def _checked(request: PrintRequest, grams: dict[int, int]) -> None:
    if set(grams) - {choice.id for choice in request.choices}:
        raise Refused.invalid({_GRAMS: _NOT_ITS_CHOICES})
    found = {}
    for choice in request.choices:
        given = grams.get(choice.id)
        if given is None:
            found[_grams_problem(str(choice.id))] = _GRAMS_NEEDED
        elif not _grams_in_range(given):
            found[_grams_problem(str(choice.id))] = _GRAMS_RANGE
    if found:
        raise Refused.invalid(found)


def _give_products(
    session: Session, request: PrintRequest, user: User | None, now: datetime
) -> None:
    """Give each catalog color choice with no linked product a "From the catalog" one, so
    its short lands on the shopping list. A color the catalog has dropped gets none."""
    for choice in request.choices:
        if choice.catalog_uuid is None:
            continue
        try:
            shopping_list.product_for_color(
                session, choice.catalog_uuid, user.id if user else None, now
            )
        except UnknownColor:
            continue


def _hold(session: Session, request: PrintRequest, grams: dict[int, int], now: datetime) -> bool:
    """Check the grams, give each choice its grams and hold them; whether every choice is
    covered."""
    _checked(request, grams)
    covered = True
    for choice in request.choices:
        choice.grams = grams[choice.id]
        placed = holds.place(
            session, holder(choice), product_id(session, choice), choice.grams, now
        )
        covered = covered and placed.short == 0
    return covered


def _approve(
    session: Session,
    request: PrintRequest,
    *,
    expected: RequestStatus,
    grams: dict[int, int],
    movers: set[Mover],
    user: User | None,
    note: str,
    now: datetime,
) -> Moved:
    """Approve with grams per choice ID, hold them and move on. Refused as `make_move` is,
    or refused INVALID per choice for missing or out-of-range grams."""
    approved = pipeline.make_move(
        request,
        expected=expected,
        to_status=RequestStatus.APPROVED,
        movers=movers,
        user=user,
        note=note,
        now=now,
    )
    _checked(request, grams)
    _give_products(session, request, user, now)
    covered = _hold(session, request, grams, now)
    landing = RequestStatus.QUEUED if covered else RequestStatus.WAITING_ON_FILAMENT
    pipeline.make_move(
        request,
        expected=RequestStatus.APPROVED,
        to_status=landing,
        movers={Mover.AUTOMATIC},
        user=None,
        note="",
        now=now,
    )
    return Moved(approved.request, approved.move, approved.user, approved.note, then=landing)


def _reprint(
    session: Session,
    request: PrintRequest,
    *,
    grams: dict[int, int],
    movers: set[Mover],
    user: User | None,
    note: str,
    now: datetime,
) -> Moved:
    """Reprint a Failed request with grams per choice ID, hold them, and land on Queued when
    covered or on Waiting on Filament when not. Refused as `_approve` is."""
    from_status, to_status = pipeline.REPRINT
    rule, cleaned = pipeline.check_move(
        request, expected=from_status, to_status=to_status, movers=movers, note=note
    )
    if not _hold(session, request, grams, now):
        rule = pipeline.landing(rule, RequestStatus.WAITING_ON_FILAMENT)
    return pipeline.record(request, rule, user=user, note=cleaned, now=now)


def make_move(
    session: Session,
    request: PrintRequest,
    *,
    expected: RequestStatus,
    to_status: RequestStatus,
    grams: dict[int, int],
    movers: set[Mover],
    user: User | None,
    note: str,
    now: datetime,
) -> Moved:
    """Move the request on as `pipeline.make_move` does, holding or releasing its filament
    as the move needs: Approve and Reprint hold `grams`, and Done, Failed and Cancelled
    release."""
    if to_status is RequestStatus.APPROVED:
        return _approve(
            session,
            request,
            expected=expected,
            grams=grams,
            movers=movers,
            user=user,
            note=note,
            now=now,
        )
    if (expected, to_status) == pipeline.REPRINT:
        return _reprint(session, request, grams=grams, movers=movers, user=user, note=note, now=now)
    moved = pipeline.make_move(
        request,
        expected=expected,
        to_status=to_status,
        movers=movers,
        user=user,
        note=note,
        now=now,
    )
    if grams:
        raise Refused.invalid({_GRAMS: _ONLY_ON_APPROVE})
    reason = _RELEASES.get(to_status)
    if reason is not None:
        for choice in request.choices:
            holds.release(session, holder(choice), reason, now)
    return moved


# Short and available grams


def short(session: Session) -> dict[int, int]:
    """How short each choice with grams of a request that holds filament is, by choice ID.
    An over-held spool's grams left go to the requests in Active-tab order, and a request's
    choices in the order they were added; a Printing request's holds take none of them."""
    query = select(PrintRequest).where(PrintRequest.status.in_(pipeline.HOLDING))
    targets: dict[holds.Holder, int] = {}
    for request in sorted(session.scalars(query), key=sort_key):
        for choice in sorted(request.choices, key=lambda c: c.id):
            if choice.grams is not None:
                targets[holder(choice)] = choice.grams
    return {held.id: grams for held, grams in holds.short(session, targets).items()}


def request_short(session: Session, request: PrintRequest) -> dict[int, int]:
    """How short the request's choices with grams are, by choice ID, while it holds
    filament; empty otherwise."""
    if request.status not in pipeline.HOLDING:
        return {}
    every = short(session)
    return {c.id: every[c.id] for c in request.choices if c.id in every}


def available(session: Session, choice: FilamentChoice) -> int:
    """The grams not held of the product the choice would be held on (0 with none)."""
    found = product_id(session, choice)
    return 0 if found is None else holds.product_available(session, found)


# The retry when stock changes


def _changed_by_hand(session: Session, request: PrintRequest) -> None:
    """Note that the request's holds were changed by hand in this transaction, so its retry
    only checks it."""
    session.info.setdefault(_CHANGED_BY_HAND, set()).add(request.id)


def _wanted(request: PrintRequest) -> list[FilamentChoice] | None:
    """The choices of a request waiting for filament whose choices all have grams; else None
    (approved before grams were asked, or not waiting)."""
    if request.status not in _WAITING:
        return None
    if any(c.grams is None for c in request.choices):
        return None
    return list(request.choices)


def _covered(session: Session, wanted: list[FilamentChoice]) -> bool:
    short_by_choice = short(session)
    return all(short_by_choice[c.id] == 0 for c in wanted)


def _hold_more(session: Session, wanted: list[FilamentChoice], now: datetime) -> bool:
    """Hold more for each short choice, toward its grams; whether every choice is covered."""
    short_by_choice = short(session)
    covered = True
    for choice in wanted:
        missing = short_by_choice[choice.id]
        if missing:
            found = product_id(session, choice)
            missing = holds.place(session, holder(choice), found, missing, now).short
        covered = covered and missing == 0
    return covered


def _queue(request: PrintRequest, now: datetime) -> None:
    pipeline.make_move(
        request,
        expected=request.status,
        to_status=RequestStatus.QUEUED,
        movers={Mover.AUTOMATIC},
        user=None,
        note="",
        now=now,
    )


def retry(session: Session) -> None:
    """Retry the requests waiting for filament, in Active-tab order, after stock changed. A
    request whose choices have no grams yet (approved before grams were asked) is left. A
    request whose holds were changed by hand in this transaction is only checked, so the
    retry its change set off doesn't undo it; later retries treat it as any other."""
    now = utcnow()
    by_hand: set[int] = session.info.pop(_CHANGED_BY_HAND, set())
    waiting = session.scalars(select(PrintRequest).where(PrintRequest.status.in_(_WAITING)))
    for request in sorted(waiting, key=sort_key):
        if request.id in by_hand:
            _check(session, request, now)
        else:
            _retry_one(session, request, now)
    session.flush()


def _retry_one(session: Session, request: PrintRequest, now: datetime) -> None:
    """Hold more for a request waiting for filament, and queue it once every choice is
    covered."""
    wanted = _wanted(request)
    if wanted is not None and _hold_more(session, wanted, now):
        _queue(request, now)


def _check(session: Session, request: PrintRequest, now: datetime) -> None:
    """Queue a request waiting for filament once every choice is covered, without holding
    more for it; nothing for any other request."""
    wanted = _wanted(request)
    if wanted is not None and _covered(session, wanted):
        _queue(request, now)


# Holds by hand


def _changing(request: PrintRequest, expected: RequestStatus) -> None:
    if request.status != expected:
        raise Refused.stale(pipeline.STALE)
    if request.status not in pipeline.HOLDING:
        raise Refused.forbidden(NOT_NOW)


def _changed(session: Session, request: PrintRequest, user: User, now: datetime) -> None:
    """Record the change and check the request again, without holding more for it: in this
    transaction, the retry that a release sets off only checks it too."""
    request.history.append(RequestHistory(kind=HistoryKind.HOLDS_CHANGED, user=user, at=now))
    request.updated_at = now
    _changed_by_hand(session, request)
    session.flush()
    _check(session, request, now)
    session.flush()


def _grams(grams: int) -> None:
    if not _grams_in_range(grams):
        raise Refused.invalid({_GRAMS: _GRAMS_RANGE})


def _choice_of(request: PrintRequest, choice_id: int) -> FilamentChoice:
    found = next((c for c in request.choices if c.id == choice_id), None)
    if found is None:
        raise Refused.not_found(_NO_SUCH_CHOICE)
    return found


def set_grams(
    session: Session,
    request: PrintRequest,
    choice_id: int,
    *,
    expected: RequestStatus,
    grams: int,
    user: User,
    now: datetime,
) -> None:
    """Give the choice new grams and hold them again, as Approve does."""
    _changing(request, expected)
    choice = _choice_of(request, choice_id)
    _grams(grams)
    holds.release(session, holder(choice), ReleaseReason.CHANGED, now)
    choice.grams = grams
    holds.place(session, holder(choice), product_id(session, choice), grams, now)
    _changed(session, request, user, now)


def _hold_of(session: Session, request: PrintRequest, hold_id: int) -> SpoolHold:
    """The request's hold; refused STALE when it was released since (changed by someone else)."""
    found = session.get(SpoolHold, hold_id)
    choices = {holder(c) for c in request.choices}
    if found is None or holds.Holder(found.holder_type, found.holder_id) not in choices:
        raise Refused.not_found(_NO_SUCH_HOLD)
    if found.released_at is not None:
        raise Refused.stale(pipeline.STALE)
    return found


def _hold_by_hand(
    session: Session, choice: FilamentChoice, spool_id: int, grams: int, now: datetime
) -> None:
    """Hold grams of a Sealed or Open spool for the choice, no more than it has available
    (any amount when its grams are unknown)."""
    _grams(grams)
    spool = session.get(Spool, spool_id)
    if spool is None or spool.state not in holds.IN_STOCK:
        raise Refused.invalid({_SPOOL: _NOT_ON_THE_SHELF})
    spool_available = holds.spool_available(session, spool)
    if spool_available is not None and grams > spool_available:
        raise Refused.invalid({_GRAMS: f"This spool has about {spool_available:,} g available."})
    holds.hold(session, holder(choice), spool, grams, now)


def add_hold(
    session: Session,
    request: PrintRequest,
    choice_id: int,
    *,
    expected: RequestStatus,
    spool_id: int,
    grams: int,
    user: User,
    now: datetime,
) -> None:
    """Hold grams of a spool, of any product, for the choice."""
    _changing(request, expected)
    _hold_by_hand(session, _choice_of(request, choice_id), spool_id, grams, now)
    _changed(session, request, user, now)


def change_hold(
    session: Session,
    request: PrintRequest,
    hold_id: int,
    *,
    expected: RequestStatus,
    spool_id: int,
    grams: int,
    user: User,
    now: datetime,
) -> None:
    """Replace one of the request's holds with grams of a spool: the same spool or another."""
    _changing(request, expected)
    found = _hold_of(session, request, hold_id)
    choice = _choice_of(request, found.holder_id)
    holds.release_hold(session, found, ReleaseReason.CHANGED, now)
    _hold_by_hand(session, choice, spool_id, grams, now)
    _changed(session, request, user, now)


def remove_hold(
    session: Session,
    request: PrintRequest,
    hold_id: int,
    *,
    expected: RequestStatus,
    user: User,
    now: datetime,
) -> None:
    """Release one of the request's holds."""
    _changing(request, expected)
    holds.release_hold(session, _hold_of(session, request, hold_id), ReleaseReason.CHANGED, now)
    _changed(session, request, user, now)
