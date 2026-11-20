"""A spool's net weight and grams left (ADR-0019): figures on the spool, not events.

- Net weight comes from the tag's filament weight. A spool with none takes its product's
  catalog color's size weight when that color has exactly one size, otherwise 1000 g.
- Grams left is the net weight on Received, and net weight x remaining % whenever the AMS
  writes a new remaining %. An Admin can set either by hand.

Callers own the transaction: nothing here commits.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import CatalogSize
from filament_tracker.db.models import Product, Spool, Tag
from filament_tracker.domain.enums import SpoolState

FALLBACK_NET_WEIGHT_G = 1000
MAX_NET_WEIGHT_G = 10_000


def tag_net_weight(tags: Iterable[Tag]) -> int | None:
    """The filament weight from the first decoded tag that has one."""
    for tag in tags:
        weight = (tag.decoded_json or {}).get("spool_weight_g")
        if isinstance(weight, int) and weight > 0:
            return weight
    return None


def fallback_net_weight(session: Session, product: Product) -> int:
    """The net weight of a spool without a tag weight."""
    color = product.catalog_manual_uuid or product.catalog_auto_uuid
    if color is None:
        return FALLBACK_NET_WEIGHT_G
    weights = session.scalars(
        select(CatalogSize.filament_weight).where(CatalogSize.variant_uuid == color)
    ).all()
    return round(weights[0]) if len(weights) == 1 else FALLBACK_NET_WEIGHT_G


def give_fallback_net_weight(session: Session, spool: Spool) -> None:
    """A new spool with no tag weight takes the fallback."""
    if spool.net_weight_g is None:
        spool.net_weight_g = fallback_net_weight(session, spool.product)


def take_tag_net_weight(spool: Spool, tag: Tag) -> None:
    """A tag newly linked to the spool sets its net weight; a tag without one changes nothing.
    A Sealed spool is full, so its grams left follows."""
    weight = tag_net_weight([tag])
    if weight is not None:
        spool.net_weight_g = weight
        if spool.state is SpoolState.SEALED:
            spool.grams_left_g = weight


def set_by_hand(spool: Spool, net_weight_g: int | None, grams_left_g: int | None) -> dict[str, str]:
    """An Admin's edit: net weight from 1 to 10,000 g, grams left from 0 to net weight. Pass
    the spool's own value for a field left unchanged (grams left may stay unknown). Returns
    the problems, if any, and then changes nothing."""
    problems: dict[str, str] = {}
    if net_weight_g is None or not 1 <= net_weight_g <= MAX_NET_WEIGHT_G:
        problems["net_weight_g"] = f"Net weight must be 1 to {MAX_NET_WEIGHT_G:,} g."
    elif grams_left_g is not None and not 0 <= grams_left_g <= net_weight_g:
        problems["grams_left_g"] = f"Grams left must be 0 to the net weight, {net_weight_g:,} g."
    if not problems:
        spool.net_weight_g = net_weight_g
        spool.grams_left_g = grams_left_g
    return problems


def received(spool: Spool) -> None:
    """Received: the spool is full."""
    spool.grams_left_g = spool.net_weight_g


def from_remaining_pct(spool: Spool) -> None:
    """The AMS wrote a new remaining %: grams left follows it, over any hand figure."""
    if spool.net_weight_g is not None and spool.remaining_pct is not None:
        spool.grams_left_g = round(spool.net_weight_g * spool.remaining_pct / 100)
