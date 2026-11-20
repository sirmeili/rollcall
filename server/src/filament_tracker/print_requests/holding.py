"""Grams and holds on filament choices, and Approve, which places them.

Each choice is a holder in Inventory's hold service, as `filament_choice` and its ID. A
product choice is held on that product; a catalog color choice on the product whose
effective catalog link is that color, and with none, all its grams are short. A choice is
covered when its shortfall is 0.

Approve takes grams for every choice, from 1 to 100,000, for the whole quantity. In one
transaction it records Approved by the Admin, places holds, and moves on automatically, with
no user: to Queued when every choice is covered, otherwise to Waiting on Filament.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.request_models import FilamentChoice, PrintRequest
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import pipeline
from filament_tracker.print_requests.pipeline import Moved, Mover
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
ONLY_ON_APPROVE = "Grams are given only when approving."

# Where a request's choices are held and may be short.
HOLDING = (RequestStatus.APPROVED, RequestStatus.WAITING_ON_FILAMENT, RequestStatus.QUEUED)


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
    _checked(request, grams)
    covered = True
    for choice in request.choices:
        choice.grams = grams[choice.id]
        placed = holds.place(
            session, holder(choice), product_id(session, choice), choice.grams, now
        )
        covered = covered and placed.short == 0
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


def shortfall(session: Session, request: PrintRequest, choice: FilamentChoice) -> int | None:
    """The choice's grams not yet held, while the request holds filament; else None."""
    if choice.grams is None or request.status not in HOLDING:
        return None
    return holds.shortfall(session, holder(choice), choice.grams)


def available(session: Session, choice: FilamentChoice) -> int:
    """The grams not held of the product the choice would be held on (0 with none)."""
    found = product_id(session, choice)
    return 0 if found is None else holds.product_available(session, found)
