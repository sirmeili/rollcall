"""Filament choices: what each one may be when chosen, and how each is shown later.

A choice is a product with at least one Sealed or Open spool when it is chosen, or a catalog
color, kept by its OFDB UUID (ADR-0016). A product with no spools in stock is offered only
through its linked catalog color. Once made, a choice keeps its product or color whatever
happens to the stock; a catalog color that later leaves the catalog reads as no longer in it.

Shown with each: a product's Sealed and Open counts now; a catalog color's similar in-stock
colors, as the Catalog page finds them (none for a multi-color one).
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.db.request_models import FilamentChoice
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services.catalog_links import CatalogIndex, load_index
from filament_tracker.services.catalog_read import CatalogColor, FilamentLine, SimilarColor
from filament_tracker.services.catalog_read import read_catalog as read_whole_catalog
from filament_tracker.services.queries import inventory

PRODUCT = "product"
CATALOG_COLOR = "catalog_color"


@dataclass(frozen=True)
class ChoiceInput:
    product_id: int | None
    catalog_color: str | None
    note: str

    @property
    def key(self) -> tuple[str, int | str | None]:
        if self.product_id is not None:
            return PRODUCT, self.product_id
        return CATALOG_COLOR, self.catalog_color


def choice_key(choice: FilamentChoice) -> tuple[str, int | str | None]:
    if choice.product_id is not None:
        return PRODUCT, choice.product_id
    return CATALOG_COLOR, choice.catalog_uuid


def _stock(session: Session) -> dict[int, tuple[int, int]]:
    """Each product's Sealed and Open spool counts."""
    return {
        item.product.id: (
            item.counts.get(SpoolState.SEALED, 0),
            item.counts.get(SpoolState.OPEN, 0),
        )
        for item in inventory(session)
    }


def make_choices(
    session: Session, inputs: list[ChoiceInput], kept: list[FilamentChoice]
) -> tuple[list[FilamentChoice], str | None]:
    """The choices to save, in order, or the problem with them. A choice the request already
    has is kept as it is; only new ones are checked against the stock and the catalog."""
    if not inputs:
        return [], "Add at least one filament."
    kept_by_key = {choice_key(c): c for c in kept}
    stock: dict[int, tuple[int, int]] | None = None
    index: CatalogIndex | None = None
    made = []
    for position, item in enumerate(inputs):
        old = kept_by_key.get(item.key)
        if old is not None:
            made.append(_copy(old, position, item.note))
            continue
        if item.product_id is not None:
            stock = stock if stock is not None else _stock(session)
            sealed, open_ = stock.get(item.product_id, (0, 0))
            if sealed + open_ == 0:
                return [], "Pick products with a Sealed or Open spool, or a catalog color."
            made.append(
                FilamentChoice(position=position, product_id=item.product_id, note=item.note)
            )
        else:
            index = index if index is not None else load_index(session)
            color = index.colors.get(item.catalog_color or "")
            if color is None:
                return [], "One of the catalog colors isn't in the catalog."
            made.append(
                FilamentChoice(
                    position=position,
                    catalog_uuid=color.uuid,
                    catalog_line=color.line,
                    catalog_name=color.name,
                    catalog_hexes=color.hexes,
                    note=item.note,
                )
            )
    return made, None


def _copy(old: FilamentChoice, position: int, note: str) -> FilamentChoice:
    return FilamentChoice(
        position=position,
        product_id=old.product_id,
        catalog_uuid=old.catalog_uuid,
        catalog_line=old.catalog_line,
        catalog_name=old.catalog_name,
        catalog_hexes=old.catalog_hexes,
        note=note,
    )


# --- Showing choices ---------------------------------------------------------------------


@dataclass(frozen=True)
class ShownChoice:
    kind: str
    note: str
    name: str
    # RRGGBB, the main color first.
    hexes: list[str]
    material: str | None = None
    product_id: int | None = None
    sealed: int | None = None
    open: int | None = None
    catalog_color: str | None = None
    # A catalog color's own name and its filament line's, for Find in store.
    color_name: str | None = None
    line: str | None = None
    bambu_code: str | None = None
    in_catalog: bool = True
    multi_color: bool = False
    similar: list[SimilarColor] = field(default_factory=list)


def _catalog_name(line: str | None, name: str | None) -> str:
    return " ".join(part for part in (name, line) if part)


def swatch(choice: FilamentChoice) -> tuple[str, list[str]]:
    """A choice's name and colors, as noted when it was chosen (for the list)."""
    if choice.product is not None:
        return choice.product.display_name, [choice.product.color_rgba[:6].upper()]
    return _catalog_name(choice.catalog_line, choice.catalog_name), list(choice.catalog_hexes or [])


class ChoiceReader:
    """Shows choices with the stock and catalog as they are now, loading each once."""

    def __init__(self, session: Session, cutoff: float, store_address: str) -> None:
        self._session = session
        self._cutoff = cutoff
        self._store_address = store_address
        self._stock: dict[int, tuple[int, int]] | None = None
        self._colors: dict[str, tuple[FilamentLine, CatalogColor]] | None = None
        self._moved: dict[str, list[str]] = {}

    def _stock_now(self) -> dict[int, tuple[int, int]]:
        if self._stock is None:
            self._stock = _stock(self._session)
        return self._stock

    def _catalog(self) -> dict[str, tuple[FilamentLine, CatalogColor]]:
        if self._colors is None:
            catalog = read_whole_catalog(self._session, self._cutoff, self._store_address)
            self._colors = {c.uuid: (line, c) for line in catalog.lines for c in line.colors}
            self._moved = load_index(self._session).moved
        return self._colors

    def _find(self, uuid: str) -> tuple[FilamentLine, CatalogColor] | None:
        colors = self._catalog()
        if uuid in colors:
            return colors[uuid]
        # OFDB merged it into another color: follow the merge, as catalog links do.
        moved = self._moved.get(uuid, [])
        return colors[moved[0]] if len(moved) == 1 and moved[0] in colors else None

    def show(self, choice: FilamentChoice) -> ShownChoice:
        if choice.product is not None:
            return self._product(choice.product, choice.note)
        found = self._find(choice.catalog_uuid or "")
        if found is None:
            return ShownChoice(
                kind=CATALOG_COLOR,
                note=choice.note,
                name=_catalog_name(choice.catalog_line, choice.catalog_name),
                hexes=list(choice.catalog_hexes or []),
                catalog_color=choice.catalog_uuid,
                color_name=choice.catalog_name,
                line=choice.catalog_line,
                in_catalog=False,
                multi_color=len(choice.catalog_hexes or []) > 1,
            )
        line, color = found
        return ShownChoice(
            kind=CATALOG_COLOR,
            note=choice.note,
            name=_catalog_name(line.name, color.name),
            hexes=color.hexes,
            material=line.material,
            catalog_color=color.uuid,
            color_name=color.name,
            line=line.name,
            bambu_code=color.bambu_code,
            multi_color=color.multi_color,
            similar=color.similar,
        )

    def _product(self, product: Product, note: str) -> ShownChoice:
        sealed, open_ = self._stock_now().get(product.id, (0, 0))
        return ShownChoice(
            kind=PRODUCT,
            note=note,
            name=product.display_name,
            hexes=[product.color_rgba[:6].upper()],
            material=product.filament_type,
            product_id=product.id,
            sealed=sealed,
            open=open_,
        )
