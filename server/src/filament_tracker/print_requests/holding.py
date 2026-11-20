"""Grams and holds on filament choices, and Approve, which places them.

Each choice is a holder in Inventory's hold service, as `filament_choice` and its ID. A
product choice is held on that product; a catalog color choice on the product whose
effective catalog link is that color, and with none, all its grams are short. A choice is
covered when its shortfall is 0.

Approve takes grams for every choice, from 1 to 100,000, for the whole quantity. In one
transaction it records Approved by the Admin, places holds, and moves on automatically, with
no user: to Queued when every choice is covered, otherwise to Waiting on Filament.

Reprint takes grams for every choice in the same way, pre-filled on the page from the last
attempt's. It places holds and lands on Queued when every choice is covered, otherwise on
Waiting on Filament: one move by the Admin either way, with no email.

The moves to Done, Failed and Cancelled release the request's holds, with that reason.

When stock changes (ADR-0020), Approved and Waiting on Filament requests are retried in
Active-tab order: each short choice takes more holds, and a request with every choice
covered moves to Queued automatically, with no user and no email. A Queued request is never
moved back; one that becomes short shows its shortfall.

A signed-in Admin changes a request's holds by hand while it is Approved, Waiting on
Filament or Queued: a choice's grams (holding them again), a hold's spool or grams, a hold
on any Sealed or Open spool (of another product, say, for a similar color), or no hold. A
hold by hand takes no more than the spool has available, unless its grams are unknown. Each
change names the status it expects, releases what it replaces as `changed`, writes one
`holds_changed` entry, sends no email, and checks the request again: it moves to Queued
once covered, but takes no more holds until a later retry, so the change isn't undone.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.models import Spool, SpoolHold, User
from filament_tracker.db.request_models import FilamentChoice, PrintRequest, RequestHistory
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import HistoryKind, ReleaseReason, RequestStatus
from filament_tracker.print_requests import pipeline
from filament_tracker.print_requests.access import is_admin
from filament_tracker.print_requests.pipeline import Moved, Mover
from filament_tracker.print_requests.read import sort_key
from filament_tracker.print_requests.rules import Problems
from filament_tracker.services import holds
from filament_tracker.services.catalog_links import linked_product

HOLDER_TYPE = "filament_choice"
GRAMS_MIN = 1
GRAMS_MAX = 100_000
GRAMS = "grams"
GRAMS_NEEDED = "Give the grams for this filament."
GRAMS_RANGE = f"Grams must be {GRAMS_MIN} to {GRAMS_MAX:,}."
NOT_ITS_CHOICES = "Give grams only for its filaments."
ONLY_ON_APPROVE = "Grams are given only when approving or reprinting."
SPOOL = "spool_id"
NOT_ON_THE_SHELF = "Choose a Sealed or Open spool."
NOT_NOW = "Holds can be changed only while a request is Approved, Waiting on Filament or Queued."
NO_SUCH_CHOICE = "no such filament choice"
NO_SUCH_HOLD = "no such hold"

# The moves that release a request's holds, and why.
RELEASES = {
    RequestStatus.DONE: ReleaseReason.DONE,
    RequestStatus.FAILED: ReleaseReason.FAILED,
    RequestStatus.CANCELLED: ReleaseReason.CANCELLED,
}

# Where a request's choices are held and may be short.
HOLDING = (RequestStatus.APPROVED, RequestStatus.WAITING_ON_FILAMENT, RequestStatus.QUEUED)

# The session's requests whose holds were changed by hand, which its retry only checks.
_CHANGED_BY_HAND = "holds_changed_by_hand"

# Where a request waits for filament, and is retried when stock changes.
WAITING = (RequestStatus.APPROVED, RequestStatus.WAITING_ON_FILAMENT)


class NotFound(Exception):
    """No such choice or hold on this request."""


def holder(choice: FilamentChoice) -> holds.Holder:
    return holds.Holder(HOLDER_TYPE, choice.id)


def product_id(session: Session, choice: FilamentChoice) -> int | None:
    """The product the choice is held on, if any."""
    if choice.product_id is not None:
        return choice.product_id
    product = linked_product(session, choice.catalog_uuid or "")
    return None if product is None else product.id


def grams_problem(field: str) -> str:
    """The key a choice's grams problem is reported under: `grams.<choice ID>`."""
    return f"{GRAMS}.{field}"


def _checked(request: PrintRequest, grams: dict[int, int]) -> None:
    if set(grams) - {choice.id for choice in request.choices}:
        raise Problems({GRAMS: NOT_ITS_CHOICES})
    found = {}
    for choice in request.choices:
        given = grams.get(choice.id)
        if given is None:
            found[grams_problem(str(choice.id))] = GRAMS_NEEDED
        elif not GRAMS_MIN <= given <= GRAMS_MAX:
            found[grams_problem(str(choice.id))] = GRAMS_RANGE
    if found:
        raise Problems(found)


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


def approve(
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
    or with Problems per choice for missing or out-of-range grams."""
    approved = pipeline.make_move(
        request,
        expected=expected,
        to_status=RequestStatus.APPROVED,
        movers=movers,
        user=user,
        note=note,
        now=now,
    )
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


def reprint(
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
    covered or on Waiting on Filament when not. Refused as `approve` is."""
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
        return approve(
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
        return reprint(session, request, grams=grams, movers=movers, user=user, note=note, now=now)
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
        raise Problems({GRAMS: ONLY_ON_APPROVE})
    reason = RELEASES.get(to_status)
    if reason is not None:
        for choice in request.choices:
            holds.release(session, holder(choice), reason, now)
    return moved


def shortfall(session: Session, request: PrintRequest, choice: FilamentChoice) -> int | None:
    """The choice's grams not yet held, while the request holds filament; else None."""
    if choice.grams is None or request.status not in HOLDING:
        return None
    return holds.shortfall(session, holder(choice), choice.grams)


def available(session: Session, choice: FilamentChoice) -> int:
    """The grams not held of the product the choice would be held on (0 with none)."""
    found = product_id(session, choice)
    return 0 if found is None else holds.product_available(session, found)


def _hold_more(
    session: Session, wanted: dict[FilamentChoice, int], now: datetime, *, top_up: bool = True
) -> bool:
    """Hold more for each short choice, toward its grams (only check them, without
    `top_up`); whether every choice is covered."""
    covered = True
    for choice, grams in wanted.items():
        short = holds.shortfall(session, holder(choice), grams)
        if short and top_up:
            found = product_id(session, choice)
            short = holds.place(session, holder(choice), found, short, now).short
        covered = covered and short == 0
    return covered


def retry(session: Session) -> None:
    """Retry the requests waiting for filament, in Active-tab order, after stock changed. A
    request whose choices have no grams yet (approved before grams were asked) is left. A
    request whose holds were changed by hand in this transaction is only checked, so the
    retry its change set off doesn't undo it; later retries treat it as any other."""
    now = utcnow()
    by_hand: set[int] = session.info.pop(_CHANGED_BY_HAND, set())
    waiting = session.scalars(select(PrintRequest).where(PrintRequest.status.in_(WAITING)))
    for request in sorted(waiting, key=sort_key):
        _retry_one(session, request, now, top_up=request.id not in by_hand)
    session.flush()


def _retry_one(
    session: Session, request: PrintRequest, now: datetime, *, top_up: bool = True
) -> None:
    """Hold more for a request waiting for filament (unless not `top_up`), and queue it once
    every choice is covered; nothing for any other request."""
    if request.status not in WAITING:
        return
    wanted = {c: c.grams for c in request.choices if c.grams is not None}
    if len(wanted) < len(request.choices):
        return
    if _hold_more(session, wanted, now, top_up=top_up):
        pipeline.make_move(
            request,
            expected=request.status,
            to_status=RequestStatus.QUEUED,
            movers={Mover.AUTOMATIC},
            user=None,
            note="",
            now=now,
        )


# --- Changing holds by hand -------------------------------------------------------------------


def may_change(principal: Principal, request: PrintRequest) -> bool:
    """A signed-in Admin changes a request's holds while it is Approved, Waiting on Filament
    or Queued. Tokens act for no one, and a change records who made it."""
    return principal.user is not None and is_admin(principal) and request.status in HOLDING


def _changing(request: PrintRequest, expected: RequestStatus) -> None:
    if request.status != expected:
        raise pipeline.Stale(pipeline.STALE)
    if request.status not in HOLDING:
        raise pipeline.NotAMove(NOT_NOW)


def _changed(session: Session, request: PrintRequest, user: User, now: datetime) -> None:
    """Record the change and check the request again, without holding more for it: in this
    transaction, the retry that a release sets off only checks it too."""
    request.history.append(RequestHistory(kind=HistoryKind.HOLDS_CHANGED, user=user, at=now))
    request.updated_at = now
    session.info.setdefault(_CHANGED_BY_HAND, set()).add(request.id)
    session.flush()
    _retry_one(session, request, now, top_up=False)
    session.flush()


def _grams(grams: int) -> None:
    if not GRAMS_MIN <= grams <= GRAMS_MAX:
        raise Problems({GRAMS: GRAMS_RANGE})


def choice_of(request: PrintRequest, choice_id: int) -> FilamentChoice:
    found = next((c for c in request.choices if c.id == choice_id), None)
    if found is None:
        raise NotFound(NO_SUCH_CHOICE)
    return found


def set_grams(
    session: Session,
    request: PrintRequest,
    choice: FilamentChoice,
    *,
    expected: RequestStatus,
    grams: int,
    user: User,
    now: datetime,
) -> None:
    """Give the choice new grams and hold them again, as Approve does."""
    _changing(request, expected)
    _grams(grams)
    holds.release(session, holder(choice), ReleaseReason.CHANGED, now)
    choice.grams = grams
    holds.place(session, holder(choice), product_id(session, choice), grams, now)
    _changed(session, request, user, now)


def _hold_of(session: Session, request: PrintRequest, hold_id: int) -> SpoolHold:
    """The request's hold; Stale when it was released since (changed by someone else)."""
    found = session.get(SpoolHold, hold_id)
    choices = {holder(c) for c in request.choices}
    if found is None or holds.Holder(found.holder_type, found.holder_id) not in choices:
        raise NotFound(NO_SUCH_HOLD)
    if found.released_at is not None:
        raise pipeline.Stale(pipeline.STALE)
    return found


def _hold_by_hand(
    session: Session, choice: FilamentChoice, spool_id: int, grams: int, now: datetime
) -> None:
    """Hold grams of a Sealed or Open spool for the choice, no more than it has available
    (any amount when its grams are unknown)."""
    _grams(grams)
    spool = session.get(Spool, spool_id)
    if spool is None or spool.state not in holds.IN_STOCK:
        raise Problems({SPOOL: NOT_ON_THE_SHELF})
    available = holds.spool_available(session, spool)
    if available is not None and grams > available:
        raise Problems({GRAMS: f"This spool has about {available:,} g available."})
    holds.hold(session, holder(choice), spool, grams, now)


def add_hold(
    session: Session,
    request: PrintRequest,
    choice: FilamentChoice,
    *,
    expected: RequestStatus,
    spool_id: int,
    grams: int,
    user: User,
    now: datetime,
) -> None:
    """Hold grams of a spool, of any product, for the choice."""
    _changing(request, expected)
    _hold_by_hand(session, choice, spool_id, grams, now)
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
    choice = next(c for c in request.choices if c.id == found.holder_id)
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
