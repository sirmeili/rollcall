"""Possible duplicates: Review asks a person whether a product a scan just made is the same as
a "From the catalog" product, when the tag's catalog chain could not tell.

A scan that makes a new product, and whose tag's chain gives no catalog color, looks for
candidates: "From the catalog" products linked to a color in the filament lines the tag's
material ID gives (its BambuStudio filament ID, its Bambu codes, their OFDB lines), whose hex
is within the similarity cutoff of the tag's color. Colors in other lines never count.

Same product merges the candidate into the scanned product, which keeps its tag IDs, name,
color and spools; the candidate is deleted. Keep separate leaves both, and Bring back
reopens it, as Review's Dismiss does for other kinds.
"""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from filament_tracker.db.models import Product, Spool
from filament_tracker.db.shopping_models import (
    DuplicateCandidate,
    HandReason,
    PossibleDuplicate,
    ShoppingHistory,
    Suggestion,
)
from filament_tracker.domain.color import ciede2000, hex_to_lab
from filament_tracker.domain.enums import DuplicateState, ShoppingAction
from filament_tracker.services import stock_changes
from filament_tracker.services.catalog_links import (
    catalog_color_for_tag,
    effective_uuid,
    lines_for_material,
    load_index,
    take_manual_link,
)
from filament_tracker.services.shopping_list import arrivals, history
from filament_tracker.services.shopping_list.on_order import find_item, item_for


class NoSuchDuplicate(LookupError):
    """No possible duplicate has this ID."""


class DuplicateDecided(ValueError):
    """The possible duplicate is not in the state the change needs."""


class NotACandidate(ValueError):
    """The product is not one of the possible duplicate's candidates."""


class CandidateHasSpools(ValueError):
    """The candidate has spools, so it cannot be merged and deleted."""


def detect(
    session: Session, product: Product, variant_id: str, cutoff: float, now: datetime
) -> PossibleDuplicate | None:
    """After a scan made `product` from its tag: a possible duplicate listing every
    candidate, or None when the chain gives a catalog color or nothing is close."""
    material_id = product.material_id
    if material_id is None or catalog_color_for_tag(session, material_id, variant_id):
        return None
    lines = lines_for_material(session, material_id)
    if not lines:
        return None
    index = load_index(session)
    lab = hex_to_lab(product.color_rgba)
    waiting = select(Product).where(Product.from_catalog.is_(True))
    candidates = []
    for other in session.scalars(waiting.order_by(Product.created_at, Product.id)):
        color = index.colors.get(effective_uuid(other, index) or "")
        if color is None or color.line_uuid not in lines:
            continue
        if ciede2000(lab, hex_to_lab(color.hexes[0])) <= cutoff:
            candidates.append(other)
    if not candidates:
        return None
    session.flush()
    duplicate = PossibleDuplicate(
        product_id=product.id,
        created_at=now,
        candidates=[DuplicateCandidate(product_id=c.id) for c in candidates],
    )
    session.add(duplicate)
    return duplicate


def open_duplicates(session: Session) -> list[PossibleDuplicate]:
    """The possible duplicates waiting for a person, newest first."""
    query = (
        select(PossibleDuplicate)
        .where(PossibleDuplicate.state == DuplicateState.OPEN)
        .options(selectinload(PossibleDuplicate.candidates))
        .order_by(PossibleDuplicate.created_at.desc(), PossibleDuplicate.id.desc())
    )
    return list(session.scalars(query))


def candidates_of(session: Session, duplicate: PossibleDuplicate) -> list[Product]:
    """Its candidate products, oldest first."""
    ids = [c.product_id for c in duplicate.candidates]
    query = select(Product).where(Product.id.in_(ids)).order_by(Product.created_at, Product.id)
    return list(session.scalars(query))


def _get(session: Session, duplicate_id: int) -> PossibleDuplicate:
    duplicate = session.get(PossibleDuplicate, duplicate_id)
    if duplicate is None:
        raise NoSuchDuplicate(duplicate_id)
    return duplicate


def _decide(
    duplicate: PossibleDuplicate, state: DuplicateState, user_id: int | None, now: datetime
) -> None:
    duplicate.state = state
    duplicate.decided_by = user_id
    duplicate.decided_at = now


def same_product(
    session: Session, duplicate_id: int, candidate_id: int, user_id: int | None, now: datetime
) -> None:
    """The scanned product and the candidate are one: merge the candidate into it.

    The scanned product keeps its tag IDs, name, color and spools. It takes the candidate's
    manual catalog link, the higher threshold, its on order and its chosen size if it has
    none, and its spools then count as arriving. The candidate's hand-added reasons,
    suggestions and dismissal move to it. Its shopping list history is copied to it, since
    entries are never edited, and the candidate is deleted with its own entries. The merge
    goes into the shopping list history.
    """
    duplicate = _get(session, duplicate_id)
    if duplicate.state is not DuplicateState.OPEN:
        raise DuplicateDecided(duplicate_id)
    if candidate_id not in {c.product_id for c in duplicate.candidates}:
        raise NotACandidate(candidate_id)
    scanned = session.get_one(Product, duplicate.product_id)
    candidate = session.get_one(Product, candidate_id)
    if candidate.spools:
        raise CandidateHasSpools(candidate_id)

    take_manual_link(session, scanned, candidate)
    scanned.low_stock_threshold = max(scanned.low_stock_threshold, candidate.low_stock_threshold)
    _merge_items(session, scanned, candidate)
    for spool in session.scalars(
        select(Spool).where(Spool.product_id == scanned.id).order_by(Spool.id)
    ):
        arrivals.count_late(session, spool)
    for table in (HandReason, Suggestion):
        session.execute(
            update(table).where(table.product_id == candidate.id).values(product_id=scanned.id)
        )
    _copy_history(session, scanned, candidate)
    _drop_candidate(session, candidate, duplicate)
    _decide(duplicate, DuplicateState.SAME_PRODUCT, user_id, now)
    history.record(session, scanned.id, ShoppingAction.SAME_PRODUCT, user_id, now)
    session.delete(candidate)
    session.flush()
    stock_changes.changed(session)


def _merge_items(session: Session, scanned: Product, candidate: Product) -> None:
    """The candidate's item into the scanned product's one item."""
    other = find_item(session, candidate.id)
    if other is None:
        return
    item = item_for(session, scanned.id)
    item.on_order += other.on_order
    if other.dismissed_need is not None:
        item.dismissed_need = max(item.dismissed_need or 0, other.dismissed_need)
    if item.chosen_size_g is None:
        item.chosen_size_g = other.chosen_size_g
    session.delete(other)
    session.flush()


def _copy_history(session: Session, scanned: Product, candidate: Product) -> None:
    """New entries on the scanned product, copying the candidate's; the candidate's own are
    deleted with it."""
    query = select(ShoppingHistory).where(ShoppingHistory.product_id == candidate.id)
    for entry in session.scalars(query.order_by(ShoppingHistory.id)).all():
        session.add(
            ShoppingHistory(
                product_id=scanned.id,
                action=entry.action,
                spools=entry.spools,
                size_g=entry.size_g,
                on_order=entry.on_order,
                user_id=entry.user_id,
                at=entry.at,
            )
        )
        session.delete(entry)
    session.flush()


def _drop_candidate(session: Session, candidate: Product, keep: PossibleDuplicate) -> None:
    """The candidate leaves every possible duplicate; another one left with no candidates
    goes too."""
    query = select(DuplicateCandidate).where(DuplicateCandidate.product_id == candidate.id)
    for row in session.scalars(query).all():
        duplicate = row.duplicate
        duplicate.candidates.remove(row)
        if not duplicate.candidates and duplicate is not keep:
            session.delete(duplicate)
    session.flush()


def keep_separate(session: Session, duplicate_id: int, user_id: int | None, now: datetime) -> None:
    """They are different products: leave both, and take it out of Review. Keeping it
    separate twice changes nothing."""
    duplicate = _get(session, duplicate_id)
    if duplicate.state is DuplicateState.KEPT_SEPARATE:
        return
    if duplicate.state is not DuplicateState.OPEN:
        raise DuplicateDecided(duplicate_id)
    _decide(duplicate, DuplicateState.KEPT_SEPARATE, user_id, now)


def bring_back(session: Session, duplicate_id: int) -> None:
    """Return a possible duplicate kept separate to Review."""
    duplicate = _get(session, duplicate_id)
    if duplicate.state is not DuplicateState.KEPT_SEPARATE:
        raise DuplicateDecided(duplicate_id)
    duplicate.state = DuplicateState.OPEN
    duplicate.decided_by = None
    duplicate.decided_at = None
