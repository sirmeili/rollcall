"""Changes from the web app (Editor and up): spools, manual actions and entry, products."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from filament_tracker.api.read_schemas import ProductDetail, SpoolDetail, SpoolRow
from filament_tracker.api.spool_holders import HolderReader, Holding, spool_held
from filament_tracker.api.views import event_out, product_detail, spool_detail, spool_row
from filament_tracker.api.write_schemas import (
    ActionResult,
    BulkLocation,
    ManualAction,
    ManualSpool,
    ProductCreate,
    ProductUpdate,
    SpoolUpdate,
)
from filament_tracker.auth import DbSession, Editor, Principal, forbidden, problems
from filament_tracker.db.models import Product, Spool
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import EventType, Role
from filament_tracker.services import edits, grams, queries
from filament_tracker.services.catalog_links import ColorTaken, UnknownColor, set_manual

router = APIRouter(tags=["edits"])

# Allowance for a phone clock that runs a little fast.
CLOCK_SKEW = timedelta(minutes=5)


def _user_id(caller: Principal) -> int | None:
    return caller.user.id if caller.user else None


def _when(value: datetime | None) -> datetime:
    now = utcnow()
    if value is None:
        return now
    if value > now + CLOCK_SKEW:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "time is in the future")
    return value


def _spool(session: DbSession, spool_id: int) -> Spool:
    spool = session.get(Spool, spool_id)
    if spool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such spool")
    return spool


def _product(session: DbSession, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such product")
    return product


def _detail(
    session: DbSession, spool: Spool, holding: HolderReader, caller: Principal
) -> SpoolDetail:
    session.refresh(spool)
    held = spool_held(session, spool, holding, caller)
    return spool_detail(spool, queries.spool_events(session, spool), held)


GRAMS_FIELDS = frozenset({"net_weight_g", "grams_left_g"})


@router.patch("/spools/{spool_id}", response_model=SpoolDetail)
def update_spool(
    spool_id: int, body: SpoolUpdate, caller: Editor, session: DbSession, holding: Holding
) -> SpoolDetail:
    """Edit location and notes, and (Admins only) net weight and grams left. Fields left out
    of the body are not changed. Grams are changed in place: no event, no undo (ADR-0019)."""
    sent = body.model_fields_set
    if sent & GRAMS_FIELDS and caller.role is not Role.ADMIN:
        raise forbidden("only Admins can edit net weight and grams left")
    spool = _spool(session, spool_id)
    if sent & GRAMS_FIELDS:
        _set_grams(spool, body)
    for name in sent - GRAMS_FIELDS:
        setattr(spool, name, getattr(body, name))
    session.commit()
    return _detail(session, spool, holding, caller)


def _set_grams(spool: Spool, body: SpoolUpdate) -> None:
    sent = body.model_fields_set
    if "grams_left_g" in sent and body.grams_left_g is None:
        raise problems({"grams_left_g": "Grams left can't be cleared."})
    found = grams.set_by_hand(
        spool,
        body.net_weight_g if "net_weight_g" in sent else spool.net_weight_g,
        body.grams_left_g if "grams_left_g" in sent else spool.grams_left_g,
    )
    if found:
        raise problems(found)


@router.patch("/spools", response_model=list[SpoolRow])
def move_spools(body: BulkLocation, _: Editor, session: DbSession) -> list[SpoolRow]:
    """Set the location of several spools; all must exist, or nothing changes."""
    try:
        spools = edits.set_location(session, body.spool_ids, body.location)
    except edits.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    session.commit()
    return [spool_row(s) for s in spools]


@router.post("/spools/{spool_id}/events", response_model=ActionResult)
def manual_action(
    spool_id: int, body: ManualAction, caller: Editor, session: DbSession, holding: Holding
) -> ActionResult:
    """Record received, opened or empty by hand, with the same rules as a scan."""
    spool = _spool(session, spool_id)
    result = edits.record_action(
        session,
        spool,
        EventType(body.action.value),
        _when(body.occurred_at),
        user_id=_user_id(caller),
    )
    session.commit()
    return ActionResult(
        outcome=result.step.outcome.value,
        event=event_out(result.event),
        spool=_detail(session, spool, holding, caller),
    )


@router.post("/spools", response_model=SpoolDetail, status_code=status.HTTP_201_CREATED)
def add_spool(
    body: ManualSpool, caller: Editor, session: DbSession, holding: Holding
) -> SpoolDetail:
    """Manual entry: a placeholder spool, recorded as received, linked to its tag on the
    first scan of that product."""
    product = _product(session, body.product_id)
    spool = edits.add_placeholder(
        session,
        product,
        _when(body.received_at),
        user_id=_user_id(caller),
        location=body.location,
        notes=body.notes,
    )
    session.commit()
    return _detail(session, spool, holding, caller)


@router.post("/products", response_model=ProductDetail, status_code=status.HTTP_201_CREATED)
def add_product(body: ProductCreate, _: Editor, session: DbSession) -> ProductDetail:
    """A provisional product, merged into the real one when one of its tags is scanned."""
    product = Product(**body.model_dump(), provisional=True)
    session.add(product)
    session.commit()
    return product_detail(product)


@router.patch("/products/{product_id}", response_model=ProductDetail)
def update_product(
    product_id: int, body: ProductUpdate, caller: Editor, session: DbSession
) -> ProductDetail:
    """Set the display name, low-stock threshold or nearly-out %, or link the product to a
    catalog color by hand (null clears that link). Fields left out are not changed."""
    product = _product(session, product_id)
    for name in body.model_fields_set - {"catalog_color"}:
        value = getattr(body, name)
        if value is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name} cannot be null")
        setattr(product, name, value)
    if "catalog_color" in body.model_fields_set:
        try:
            set_manual(session, product, body.catalog_color, _user_id(caller), utcnow())
        except UnknownColor:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "no such catalog color"
            ) from None
        except ColorTaken as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    session.commit()
    return product_detail(product)
