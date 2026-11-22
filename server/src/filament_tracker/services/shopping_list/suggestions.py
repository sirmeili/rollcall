"""Suggestions: a Viewer's ask to buy spools of a product or a catalog color. One counts toward
nothing until an Editor or Admin adds it, which makes it a hand-added reason, or dismisses it.
A suggested catalog color gets its "From the catalog" product only when it is added, so a
suggestion never acted on leaves nothing behind.

Suggesting, adding and dismissing go into the product's shopping list history. A catalog
color with no product has no item to record against, so its history starts once it has one:
the suggestion is recorded then, at the time it was made."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Product, User
from filament_tracker.db.shopping_models import HandReason, Suggestion
from filament_tracker.domain.enums import ShoppingAction, SuggestionStatus
from filament_tracker.services.catalog_links import (
    IndexedColor,
    UnknownColor,
    linked_product,
    load_index,
)
from filament_tracker.services.shopping_list import shopping_history
from filament_tracker.services.shopping_list.catalog_products import product_for_color


class NoSuchSuggestion(LookupError):
    """No suggestion has this ID."""


class SuggestionDecided(ValueError):
    """The suggestion was already added or dismissed."""


@dataclass(frozen=True)
class OpenSuggestion:
    """A suggestion waiting for an Editor or Admin: of a product, or of a catalog color no
    product was linked to when it was made."""

    id: int
    product: Product | None
    # The suggested catalog color's UUID, None for a product; and the color, also None once
    # the catalog has dropped it.
    catalog_uuid: str | None
    color: IndexedColor | None
    spools: int
    # Who suggested it: None for a token, which acts for no user.
    by: str | None
    at: datetime


def suggest(
    session: Session,
    product: Product | None,
    uuid: str | None,
    spools: int,
    user_id: int | None,
    now: datetime,
) -> Suggestion:
    """Suggest spools of a product, or of a catalog color (its UUID). A color already linked
    to a product suggests that product; one not in the catalog is refused (UnknownColor)."""
    if product is None and uuid is not None:
        product = linked_product(session, uuid)
        if product is None and uuid not in load_index(session).colors:
            raise UnknownColor(uuid)
    suggestion = Suggestion(
        product_id=product.id if product else None,
        catalog_uuid=None if product else uuid,
        spools=spools,
        suggested_by=user_id,
        suggested_at=now,
    )
    session.add(suggestion)
    session.flush()
    if product is not None:
        _record_suggested(session, product, suggestion)
    return suggestion


def _record_suggested(session: Session, product: Product, suggestion: Suggestion) -> None:
    shopping_history.record(
        session,
        product.id,
        ShoppingAction.SUGGESTED,
        suggestion.suggested_by,
        suggestion.suggested_at,
        spools=suggestion.spools,
    )


def _open(session: Session, suggestion_id: int) -> Suggestion:
    suggestion = session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise NoSuchSuggestion(suggestion_id)
    if suggestion.status is not SuggestionStatus.OPEN:
        raise SuggestionDecided(suggestion_id)
    return suggestion


def _decide(
    session: Session,
    suggestion: Suggestion,
    status: SuggestionStatus,
    product: Product | None,
    user_id: int | None,
    now: datetime,
) -> None:
    """Mark the suggestion decided and record it on the product, if it has one. A catalog
    color's suggestion is first recorded on the product it now has."""
    from_color = suggestion.product_id is None
    suggestion.status = status
    suggestion.decided_by = user_id
    suggestion.decided_at = now
    if product is None:
        return
    if from_color:
        _record_suggested(session, product, suggestion)
    action = (
        ShoppingAction.SUGGESTION_ADDED
        if status is SuggestionStatus.ADDED
        else ShoppingAction.SUGGESTION_DISMISSED
    )
    shopping_history.record(session, product.id, action, user_id, now, spools=suggestion.spools)


def add_suggestion(
    session: Session, suggestion_id: int, user_id: int | None, now: datetime
) -> HandReason:
    """Add an open suggestion: its spools become a hand-added reason by the person adding it.
    A catalog color with no linked product gets its "From the catalog" product now."""
    suggestion = _open(session, suggestion_id)
    if suggestion.catalog_uuid is not None:
        product = product_for_color(session, suggestion.catalog_uuid, user_id, now)
    else:
        product = session.get_one(Product, suggestion.product_id)
    reason = HandReason(product_id=product.id, spools=suggestion.spools, user_id=user_id, at=now)
    session.add(reason)
    _decide(session, suggestion, SuggestionStatus.ADDED, product, user_id, now)
    return reason


def dismiss_suggestion(
    session: Session, suggestion_id: int, user_id: int | None, now: datetime
) -> None:
    """Set an open suggestion aside. It adds nothing, and a catalog color gets no product."""
    suggestion = _open(session, suggestion_id)
    if suggestion.catalog_uuid is not None:
        product = linked_product(session, suggestion.catalog_uuid)
    else:
        product = session.get(Product, suggestion.product_id)
    _decide(session, suggestion, SuggestionStatus.DISMISSED, product, user_id, now)


def open_suggestions(session: Session) -> list[OpenSuggestion]:
    """The suggestions waiting for an Editor or Admin, oldest first."""
    query = (
        select(Suggestion, Product, User)
        .outerjoin(Product, Suggestion.product_id == Product.id)
        .outerjoin(User, Suggestion.suggested_by == User.id)
        .where(Suggestion.status == SuggestionStatus.OPEN)
        .order_by(Suggestion.suggested_at, Suggestion.id)
    )
    found = session.execute(query).all()
    colors = load_index(session).colors if any(s.catalog_uuid for s, _, _ in found) else {}
    return [
        OpenSuggestion(
            id=suggestion.id,
            product=product,
            catalog_uuid=suggestion.catalog_uuid,
            color=colors.get(suggestion.catalog_uuid) if suggestion.catalog_uuid else None,
            spools=suggestion.spools,
            by=user.username if user else None,
            at=suggestion.suggested_at,
        )
        for suggestion, product, user in found
    ]
