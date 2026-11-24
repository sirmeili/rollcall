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
link columns are written here: never other product fields, spools, tags or events. Working
out or setting links is a stock change (ADR-0020): what a catalog color choice is held on
may move.
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
from filament_tracker.services import stock_changes

TAG = "tag"
HAND = "hand"
# Where a session keeps the index it loaded, so a list of products loads it once.
_INDEX_KEY = "catalog_index"


@dataclass(frozen=True)
class IndexedColor:
    uuid: str
    name: str
    line: str
    # The filament line's OFDB UUID.
    line_uuid: str
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
            line_uuid=variant.filament_uuid,
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


def _tag_codes(
    session: Session, material_id: str | None = None
) -> dict[tuple[str, str], list[str]]:
    """BambuStudio's entries by the tag IDs they read as: (material ID, variant ID). Only
    those for one material ID, when given."""
    query = select(BambuColorCode)
    if material_id is not None:
        query = query.where(BambuColorCode.filament_id == material_id)
    found: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in session.scalars(query):
        variant_id = f"{entry.filament_id.removeprefix('GF')}-{entry.color_code}"
        found[(entry.filament_id, variant_id)].append(entry.bambu_code)
    return found


def _color_for_tag(
    material_id: str,
    variant_id: str,
    tag_codes: dict[tuple[str, str], list[str]],
    index: CatalogIndex,
) -> str | None:
    """The one BambuStudio entry for these tag IDs, then the one catalog color with its
    Bambu code; None when either is missing or not alone."""
    codes = tag_codes.get((material_id, variant_id), [])
    if len(codes) != 1:
        return None
    colors = index.by_code.get(codes[0], [])
    return colors[0] if len(colors) == 1 else None


def catalog_color_for_tag(session: Session, material_id: str, variant_id: str) -> str | None:
    """The catalog color a tag's material ID and variant ID give, by the automatic rule:
    its UUID, or None when the chain does not resolve to exactly one color."""
    return _color_for_tag(
        material_id, variant_id, _tag_codes(session, material_id), _session_index(session)
    )


def lines_for_material(session: Session, material_id: str) -> set[str]:
    """The filament lines (their UUIDs) a tag's material ID gives: the catalog colors sold
    under the Bambu codes BambuStudio lists for it, and their lines."""
    index = _session_index(session)
    codes = {code for found in _tag_codes(session, material_id).values() for code in found}
    return {index.colors[uuid].line_uuid for code in codes for uuid in index.by_code.get(code, [])}


def _automatic(
    product: Product, tag_codes: dict[tuple[str, str], list[str]], index: CatalogIndex
) -> str | None:
    if product.provisional or not product.material_id or not product.variant_id:
        return None
    return _color_for_tag(product.material_id, product.variant_id, tag_codes, index)


def _relinked(session: Session) -> None:
    """Links were worked out or set: drop the loaded index, and note a stock change."""
    forget_index(session)
    stock_changes.changed(session)


def link_product(session: Session, product: Product) -> None:
    """Work out one product's automatic link, when a scan creates or fills it in."""
    product.catalog_auto_uuid = _automatic(product, _tag_codes(session), load_index(session))
    _relinked(session)


def update_links(session: Session) -> None:
    """After a sync: work out every automatic link, move manual links along OFDB's merges,
    and note each manual link's line and color name while it is in the catalog. A sync can
    change any product's effective link, even one whose stored link stays (its color left the
    catalog), so it is always a stock change."""
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
    _relinked(session)


# --- Manual links ------------------------------------------------------------------------


class UnknownColor(LookupError):
    """No catalog color has this UUID."""


class ColorTaken(ValueError):
    """Another product is already linked to this catalog color."""

    def __init__(self, other: Product) -> None:
        super().__init__(f"{other.display_name} is already linked to that color.")
        self.other = other


def linked_products(session: Session, uuid: str) -> list[Product]:
    """The products whose effective link is this catalog color, oldest first. A manual link
    is refused while another product has it, but automatic links can still share one."""
    index = _session_index(session)
    query = select(Product).order_by(Product.created_at, Product.id)
    return [p for p in session.scalars(query) if effective_uuid(p, index) == uuid]


def linked_product(session: Session, uuid: str) -> Product | None:
    """The product a catalog color is linked to, following OFDB's merge of the color as
    manual links do. Should automatic links give it several, the oldest."""
    index = _session_index(session)
    moved = index.moved.get(uuid, [])
    if uuid not in index.colors and len(moved) == 1:
        uuid = moved[0]
    return next(iter(linked_products(session, uuid)), None)


def set_manual(
    session: Session, product: Product, uuid: str | None, user_id: int | None, now: datetime
) -> None:
    """Link the product to a catalog color by hand, or clear its manual link (None). A color
    is the link of at most one product: one another product has is refused (ColorTaken)."""
    if uuid is None:
        product.catalog_manual_uuid = product.catalog_manual_by = None
        product.catalog_manual_at = None
        product.catalog_manual_line = product.catalog_manual_name = None
    else:
        color = _session_index(session).colors.get(uuid)
        if color is None:
            raise UnknownColor(uuid)
        other = next((p for p in linked_products(session, uuid) if p.id != product.id), None)
        if other is not None:
            raise ColorTaken(other)
        product.catalog_manual_uuid = uuid
        product.catalog_manual_by = user_id
        product.catalog_manual_at = now
        product.catalog_manual_line, product.catalog_manual_name = color.line, color.name
    _relinked(session)


def take_manual_link(session: Session, product: Product, other: Product) -> None:
    """Move another product's manual link onto this one, when a possible duplicate's Same
    product makes them one. Nothing changes when the other has none."""
    if other.catalog_manual_uuid is None:
        return
    product.catalog_manual_uuid = other.catalog_manual_uuid
    product.catalog_manual_by = other.catalog_manual_by
    product.catalog_manual_at = other.catalog_manual_at
    product.catalog_manual_line = other.catalog_manual_line
    product.catalog_manual_name = other.catalog_manual_name
    other.catalog_manual_uuid = other.catalog_manual_by = None
    other.catalog_manual_at = None
    other.catalog_manual_line = other.catalog_manual_name = None
    _relinked(session)


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


def effective_color(session: Session, product: Product) -> IndexedColor | None:
    """The catalog color a product is linked to, if it is in the catalog."""
    index = _session_index(session)
    return index.colors.get(effective_uuid(product, index) or "")


def linked_product_ids(session: Session) -> set[int]:
    """The IDs of the products with an effective link."""
    index = load_index(session)
    return {p.id for p in session.scalars(select(Product)) if effective_uuid(p, index)}


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
