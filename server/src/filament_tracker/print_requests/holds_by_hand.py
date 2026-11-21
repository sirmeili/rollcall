"""Changing a request's holds by hand.

A signed-in Admin changes a request's holds while it is Approved, Waiting on Filament or
Queued: a choice's grams (holding them again), a hold's spool or grams, a hold on any Sealed
or Open spool (of another product, say, for a similar color), or no hold. A hold by hand takes
no more than the spool has available, unless its grams are unknown. Each change names the
status it expects, releases what it replaces as `changed`, writes one `holds_changed` entry,
sends no email, and checks the request again: it moves to Queued once covered, but takes no
more holds until a later retry, so the change isn't undone.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from filament_tracker.db.models import Spool, SpoolHold, User
from filament_tracker.db.request_models import FilamentChoice, PrintRequest, RequestHistory
from filament_tracker.domain.enums import HistoryKind, ReleaseReason, RequestStatus
from filament_tracker.print_requests import pipeline, retrying
from filament_tracker.print_requests.holding import (
    GRAMS,
    GRAMS_RANGE,
    grams_in_range,
    holder,
    product_id,
)
from filament_tracker.print_requests.rules import Problems
from filament_tracker.services import holds

SPOOL = "spool_id"
NOT_ON_THE_SHELF = "Choose a Sealed or Open spool."
NOT_NOW = "Holds can be changed only while a request is Approved, Waiting on Filament or Queued."
NO_SUCH_CHOICE = "no such filament choice"
NO_SUCH_HOLD = "no such hold"


class NotFound(Exception):
    """No such choice or hold on this request."""


def _changing(request: PrintRequest, expected: RequestStatus) -> None:
    if request.status != expected:
        raise pipeline.Stale(pipeline.STALE)
    if request.status not in pipeline.HOLDING:
        raise pipeline.NotAMove(NOT_NOW)


def _changed(session: Session, request: PrintRequest, user: User, now: datetime) -> None:
    """Record the change and check the request again, without holding more for it: in this
    transaction, the retry that a release sets off only checks it too."""
    request.history.append(RequestHistory(kind=HistoryKind.HOLDS_CHANGED, user=user, at=now))
    request.updated_at = now
    retrying.changed_by_hand(session, request)
    session.flush()
    retrying.check(session, request, now)
    session.flush()


def _grams(grams: int) -> None:
    if not grams_in_range(grams):
        raise Problems({GRAMS: GRAMS_RANGE})


def choice_of(request: PrintRequest, choice_id: int) -> FilamentChoice:
    found = next((c for c in request.choices if c.id == choice_id), None)
    if found is None:
        raise NotFound(NO_SUCH_CHOICE)
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
    choice = choice_of(request, choice_id)
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
    _hold_by_hand(session, choice_of(request, choice_id), spool_id, grams, now)
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
    choice = choice_of(request, found.holder_id)
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
