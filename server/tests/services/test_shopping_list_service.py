"""Inventory's shopping list service, called directly: which products are on the list, how
many spools each needs, and how the list is grouped."""

from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import (
    CatalogBrand,
    CatalogFilament,
    CatalogSize,
    CatalogVariant,
)
from filament_tracker.db.models import Product, Spool
from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import shopping_list
from filament_tracker.services.shopping_list import LowStock


def product(
    session: Session,
    name: str,
    threshold: int,
    *,
    sealed: int = 0,
    filament_type: str = "PLA",
    color: str | None = None,
) -> Product:
    item = Product(
        filament_type=filament_type,
        color_rgba="102030FF",
        display_name=name,
        low_stock_threshold=threshold,
        provisional=True,
        catalog_manual_uuid=color,
    )
    session.add(item)
    session.add_all(Spool(product=item, state=SpoolState.SEALED) for _ in range(sealed))
    session.flush()
    return item


def catalog_line(session: Session, name: str, colors: dict[str, str | None]) -> None:
    """A filament line with its colors: a UUID for each, and its Bambu code or None."""
    if session.get(CatalogBrand, "brand") is None:
        session.add(CatalogBrand(uuid="brand", name="Bambu Lab"))
        session.flush()
    session.add(
        CatalogFilament(
            uuid=f"line-{name}", brand_uuid="brand", position=0, name=name, material="PLA"
        )
    )
    session.flush()
    for uuid, code in colors.items():
        session.add(
            CatalogVariant(
                uuid=uuid, filament_uuid=f"line-{name}", position=0, name=uuid, color_hex="102030"
            )
        )
        session.flush()
        session.add(
            CatalogSize(
                uuid=f"size-{uuid}", variant_uuid=uuid, filament_weight=1000, article_number=code
            )
        )
    session.flush()


def items(session: Session) -> dict[str, int]:
    """Each product on the list by name, with its spools to buy."""
    listed = shopping_list.read(session)
    found = [item for line in listed.lines for item in line.items] + listed.not_in_catalog
    return {item.product.display_name: item.to_buy for item in found}


def test_a_low_stock_product_needs_enough_spools_to_stop_being_low(session: Session) -> None:
    product(session, "Black", threshold=2, sealed=1)

    listed = shopping_list.read(session)

    [item] = listed.not_in_catalog
    assert item.product.display_name == "Black"
    assert item.to_buy == 2
    assert item.reasons == [LowStock(spools=2, sealed=1, threshold=2)]


def test_a_product_leaves_the_list_once_it_stops_being_low(session: Session) -> None:
    black = product(session, "Black", threshold=1, sealed=1)
    assert items(session) == {"Black": 1}

    session.add(Spool(product=black, state=SpoolState.SEALED))
    session.flush()

    assert items(session) == {}


def test_a_product_whose_threshold_is_0_is_never_on_the_list(session: Session) -> None:
    product(session, "Black", threshold=0, sealed=0)

    assert items(session) == {}


def test_items_are_grouped_by_filament_line_alphabetically_with_each_lines_total(
    session: Session,
) -> None:
    catalog_line(session, "PLA Matte", {"ivory": "11100", "charcoal": None})
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    product(session, "ivory matte", threshold=1, color="ivory")
    product(session, "Charcoal Matte", threshold=2, sealed=1, color="charcoal")
    product(session, "Jade White", threshold=1, sealed=1, color="jade")

    listed = shopping_list.read(session)

    assert [(line.name, line.to_buy) for line in listed.lines] == [
        ("PLA Basic", 1),
        ("PLA Matte", 4),
    ]
    assert [item.product.display_name for item in listed.lines[1].items] == [
        "Charcoal Matte",
        "ivory matte",
    ]
    assert listed.not_in_catalog == []


def test_products_with_no_catalog_link_come_last_alphabetically(session: Session) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100"})
    product(session, "Jade White", threshold=1, color="jade")
    product(session, "white PETG", threshold=1, filament_type="PETG")
    product(session, "Black", threshold=1)
    # A manual link to a color the catalog has since dropped is not in the catalog either.
    product(session, "Old Green", threshold=1, color="dropped")

    listed = shopping_list.read(session)

    assert [line.name for line in listed.lines] == ["PLA Basic"]
    assert [item.product.display_name for item in listed.not_in_catalog] == [
        "Black",
        "Old Green",
        "white PETG",
    ]


def test_an_item_carries_its_catalog_color_and_its_bambu_code(session: Session) -> None:
    catalog_line(session, "PLA Basic", {"jade": "10100", "plain": None})
    product(session, "Jade White", threshold=1, color="jade")
    product(session, "Plain", threshold=1, color="plain")

    [line] = shopping_list.read(session).lines

    assert [(item.color.name, item.color.bambu_code) for item in line.items if item.color] == [
        ("jade", "10100"),
        ("plain", None),
    ]
