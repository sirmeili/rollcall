"""Print Requests' answer to the shopping list's question: which holding requests are short
of each product, and by how much.

Wired in at start as the app's `RequestNeedsReader` (`services/shopping_list/needs.py`), so
Inventory reads it without importing Print Requests (ADR-0014, ADR-0020). The shorts are
`filament.short`'s, so an over-held spool's grams go to the requests in Active-tab order. A
request is named only for a viewer who may see it.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import FilamentChoice
from filament_tracker.print_requests import access, filament
from filament_tracker.services.shopping_list import RequestShort


def request_needs(session: Session, viewer: Principal) -> dict[int, list[RequestShort]]:
    """Each product's requests short of it, by product ID, in Active-tab order. A request
    with two choices short of one product is one reason, their grams added up. A catalog
    color choice with no product to land on is left out."""
    shorts = {choice_id: grams for choice_id, grams in filament.short(session).items() if grams}
    if not shorts:
        return {}
    choices = {
        choice.id: choice
        for choice in session.scalars(select(FilamentChoice).where(FilamentChoice.id.in_(shorts)))
    }
    grams: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    titles: dict[int, str | None] = {}
    for choice_id, short_g in shorts.items():
        choice = choices[choice_id]
        product_id = filament.product_id(session, choice)
        if product_id is None:
            continue
        request = choice.request
        grams[product_id][request.id] += short_g
        titles[request.id] = request.title if access.may_see(viewer, request) else None
    return {
        product_id: [RequestShort(rid, titles[rid], g) for rid, g in by_request.items()]
        for product_id, by_request in grams.items()
    }
