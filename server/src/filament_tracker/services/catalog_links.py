"""Catalog links: each product's tie to its catalog color (ADR-0016).

A link stores the catalog color's OFDB UUID. It is automatic when worked out from the
product's tag IDs, or manual when set by a person; the effective link is the manual one if
set, otherwise the automatic one.

The automatic rule: a product with a material ID and a variant ID, not provisional, finds
the one entry of BambuStudio's list whose filament ID is its material ID and whose filament
ID without `GF`, a hyphen and its color code is its variant ID (GFA00 and K0 give A00-K0).
That entry's Bambu code must belong to exactly one catalog color. Otherwise there is no
automatic link; names are never compared.

A manual link is never replaced automatically, except to follow an OFDB merge (`moved_from`).
One whose color has left the catalog is kept, and reads as no longer in the catalog. Only
link columns are written here: never other product fields, spools, tags or events.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from filament_tracker.db.catalog_models import (
    BambuColorCode,
    CatalogFilament,
    CatalogSize,
    CatalogVariant,
)
from filament_tracker.db.models import Product, User

TAG = "tag"
HAND = "hand"
# Where a session keeps the index it loaded, so a list of products loads it once.
_INDEX_KEY = "catalog_index"


@dataclass(frozen=True)
class IndexedColor:
    uuid: str
    name: str
    line: str
    # RRGGBB, the main color first.
    hexes: list[str]
    bambu_code: str | None


@dataclass
class CatalogIndex:
    """The catalog colors, their Bambu codes and OFDB's merges, loaded once."""

    colors: dict[str, IndexedColor] = field(default_factory=dict)
    # A Bambu code to the catalog colors sold under it.
    by_code: dict[str, list[str]] = field(default_factory=dict)
    # An old UUID to the catalog colors that list it in `moved_from`.
    moved: dict[str, list[str]] = field(default_factory=dict)


def load_index(session: Session) -> CatalogIndex:
    lines = {
        uuid: name
        for uuid, name in session.execute(select(CatalogFilament.uuid, CatalogFilament.name))
    }
    codes: dict[str, set[str]] = defaultdict(set)
    for variant_uuid, code in session.execute(
        select(CatalogSize.variant_uuid, CatalogSize.article_number).where(
            CatalogSize.article_number.is_not(None)
        )
    ):
        codes[variant_uuid].add(code)
    index = CatalogIndex()
    for variant in session.scalars(select(CatalogVariant)):
        # A color whose sizes disagree has no Bambu code.
        own = codes.get(variant.uuid, set())
        code = next(iter(own)) if len(own) == 1 else None
        index.colors[variant.uuid] = IndexedColor(
            uuid=variant.uuid,
            name=variant.name,
            line=lines[variant.filament_uuid],
            hexes=[variant.color_hex, *variant.extra_hexes],
            bambu_code=code,
        )
        if code is not None:
            index.by_code.setdefault(code, []).append(variant.uuid)
        for old in variant.moved_from:
            index.moved.setdefault(old, []).append(variant.uuid)
    return index


def _session_index(session: Session) -> CatalogIndex:
    index = session.info.get(_INDEX_KEY)
    if index is None:
        index = session.info[_INDEX_KEY] = load_index(session)
    return index


def forget_index(session: Session) -> None:
    """Drop the session's loaded index, after the catalog or a link changes."""
    session.info.pop(_INDEX_KEY, None)


# --- Automatic links ---------------------------------------------------------------------


def _tag_codes(session: Session) -> dict[tuple[str, str], list[str]]:
    """BambuStudio's entries by the tag IDs they read as: (material ID, variant ID)."""
    found: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in session.scalars(select(BambuColorCode)):
        variant_id = f"{entry.filament_id.removeprefix('GF')}-{entry.color_code}"
        found[(entry.filament_id, variant_id)].append(entry.bambu_code)
    return found


def _automatic(
    product: Product, tag_codes: dict[tuple[str, str], list[str]], index: CatalogIndex
) -> str | None:
    if product.provisional or not product.material_id or not product.variant_id:
        return None
    codes = tag_codes.get((product.material_id, product.variant_id), [])
    if len(codes) != 1:
        return None
    colors = index.by_code.get(codes[0], [])
    return colors[0] if len(colors) == 1 else None


def link_product(session: Session, product: Product) -> None:
    """Work out one product's automatic link, when a scan creates or fills it in."""
    product.catalog_auto_uuid = _automatic(product, _tag_codes(session), load_index(session))
    forget_index(session)


def update_links(session: Session) -> None:
    """After a sync: work out every automatic link, move manual links along OFDB's merges,
    and note each manual link's line and color name while it is in the catalog."""
    index = load_index(session)
    tag_codes = _tag_codes(session)
    for product in session.scalars(select(Product)):
        product.catalog_auto_uuid = _automatic(product, tag_codes, index)
        manual = product.catalog_manual_uuid
        if manual is None:
            continue
        if manual not in index.colors and len(index.moved.get(manual, [])) == 1:
            manual = product.catalog_manual_uuid = index.moved[manual][0]
        color = index.colors.get(manual)
        if color is not None:
            product.catalog_manual_line, product.catalog_manual_name = color.line, color.name
    forget_index(session)


# --- Manual links ------------------------------------------------------------------------


class UnknownColor(LookupError):
    """No catalog color has this UUID."""


def set_manual(
    session: Session, product: Product, uuid: str | None, user_id: int | None, now: datetime
) -> None:
    """Link the product to a catalog color by hand, or clear its manual link (None)."""
    if uuid is None:
        product.catalog_manual_uuid = product.catalog_manual_by = None
        product.catalog_manual_at = None
        product.catalog_manual_line = product.catalog_manual_name = None
    else:
        color = _session_index(session).colors.get(uuid)
        if color is None:
            raise UnknownColor(uuid)
        product.catalog_manual_uuid = uuid
        product.catalog_manual_by = user_id
        product.catalog_manual_at = now
        product.catalog_manual_line, product.catalog_manual_name = color.line, color.name
    forget_index(session)


# --- Reading a link ----------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogLink:
    # The catalog color; None when it is no longer in the catalog.
    color: IndexedColor | None
    how: str
    linked_by: str | None
    linked_at: datetime | None
    # For a manual link to a color the catalog has dropped: what it was.
    was_line: str | None
    was_name: str | None
    # The product's tag gives a catalog color, so clearing a manual link goes back to it.
    tag_link_exists: bool


def effective_uuid(product: Product, index: CatalogIndex) -> str | None:
    """The catalog color a product is linked to, if it is in the catalog. A manual link to
    a dropped color gives None: it does not fall back to the automatic one."""
    uuid = product.catalog_manual_uuid or product.catalog_auto_uuid
    return uuid if uuid in index.colors else None


def catalog_link(product: Product) -> CatalogLink | None:
    """The product's link as its reads show it, or None when it has none."""
    session = object_session(product)
    if session is None:  # pragma: no cover - every product read is from a session
        return None
    index = _session_index(session)
    auto = index.colors.get(product.catalog_auto_uuid or "")
    if product.catalog_manual_uuid is None:
        if auto is None:
            return None
        return CatalogLink(auto, TAG, None, None, None, None, tag_link_exists=True)
    color = index.colors.get(product.catalog_manual_uuid)
    user = session.get(User, product.catalog_manual_by) if product.catalog_manual_by else None
    return CatalogLink(
        color=color,
        how=HAND,
        linked_by=user.username if user else None,
        linked_at=product.catalog_manual_at,
        was_line=None if color else product.catalog_manual_line,
        was_name=None if color else product.catalog_manual_name,
        tag_link_exists=auto is not None,
    )
