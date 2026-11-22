"""Retrying the requests waiting for filament when stock changes (ADR-0020).

Approved and Waiting on Filament requests are retried in Active-tab order: each short choice
takes more holds, and a request with every choice covered moves to Queued automatically, with
no user and no email. A Queued request is never moved back; one that becomes short shows its
shortfall. An over-held spool's grams left go to the requests in the same order
(`holding.short`).

A request whose holds were changed by hand in this transaction is only checked, so the retry
its change set off doesn't undo it; later retries treat it as any other.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.request_models import FilamentChoice, PrintRequest
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import holding, pipeline
from filament_tracker.print_requests.pipeline import Mover
from filament_tracker.print_requests.read import sort_key
from filament_tracker.services import holds

# Where a request waits for filament, and is retried when stock changes.
WAITING = (RequestStatus.APPROVED, RequestStatus.WAITING_ON_FILAMENT)

# The session's requests whose holds were changed by hand, which its retry only checks.
_CHANGED_BY_HAND = "holds_changed_by_hand"


def changed_by_hand(session: Session, request: PrintRequest) -> None:
    """Note that the request's holds were changed by hand in this transaction, so its retry
    only checks it."""
    session.info.setdefault(_CHANGED_BY_HAND, set()).add(request.id)


def _wanted(request: PrintRequest) -> list[FilamentChoice] | None:
    """The choices of a request waiting for filament whose choices all have grams; else None
    (approved before grams were asked, or not waiting)."""
    if request.status not in WAITING:
        return None
    if any(c.grams is None for c in request.choices):
        return None
    return list(request.choices)


def _covered(session: Session, wanted: list[FilamentChoice]) -> bool:
    short = holding.short(session)
    return all(short[c.id] == 0 for c in wanted)


def _hold_more(session: Session, wanted: list[FilamentChoice], now: datetime) -> bool:
    """Hold more for each short choice, toward its grams; whether every choice is covered."""
    short_by_choice = holding.short(session)
    covered = True
    for choice in wanted:
        short = short_by_choice[choice.id]
        if short:
            found = holding.product_id(session, choice)
            short = holds.place(session, holding.holder(choice), found, short, now).short
        covered = covered and short == 0
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
    waiting = session.scalars(select(PrintRequest).where(PrintRequest.status.in_(WAITING)))
    for request in sorted(waiting, key=sort_key):
        if request.id in by_hand:
            check(session, request, now)
        else:
            _retry_one(session, request, now)
    session.flush()


def _retry_one(session: Session, request: PrintRequest, now: datetime) -> None:
    """Hold more for a request waiting for filament, and queue it once every choice is
    covered."""
    wanted = _wanted(request)
    if wanted is not None and _hold_more(session, wanted, now):
        _queue(request, now)


def check(session: Session, request: PrintRequest, now: datetime) -> None:
    """Queue a request waiting for filament once every choice is covered, without holding
    more for it; nothing for any other request."""
    wanted = _wanted(request)
    if wanted is not None and _covered(session, wanted):
        _queue(request, now)
