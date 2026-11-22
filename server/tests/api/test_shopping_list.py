"""The shopping list page's endpoint: every low-stock product as one item, grouped by
filament line, with what to buy and why."""

import pytest
from api_helpers import scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.db.catalog_models import (
    CatalogBrand,
    CatalogFilament,
    CatalogSize,
    CatalogVariant,
)
from filament_tracker.db.models import Product
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

LIST = "/api/v1/shopping-list"
JADE = "jade-white-uuid"


@pytest.fixture
def viewer(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.VIEWER)


def _jade_white_in_the_catalog(db: Session) -> None:
    db.add(CatalogBrand(uuid="bambu", name="Bambu Lab"))
    db.flush()
    db.add(
        CatalogFilament(
            uuid="pla-basic", brand_uuid="bambu", position=0, name="PLA Basic", material="PLA"
        )
    )
    db.flush()
    db.add(
        CatalogVariant(
            uuid=JADE, filament_uuid="pla-basic", position=0, name="Jade White", color_hex="F5F5F0"
        )
    )
    db.flush()
    db.add(
        CatalogSize(
            uuid="jade-1kg", variant_uuid=JADE, filament_weight=1000, article_number="10100"
        )
    )
    db.commit()


def _product(db: Session, name: str, threshold: int, color: str | None = None) -> Product:
    product = db.query(Product).filter(Product.display_name == name).one()
    product.low_stock_threshold = threshold
    product.catalog_manual_uuid = color
    db.commit()
    return product


def test_an_empty_list(viewer: TestClient) -> None:
    response = viewer.get(LIST)

    assert response.status_code == 200
    assert response.json() == {
        "lines": [],
        "not_in_catalog": [],
        "store_address": "https://us.store.bambulab.com",
    }


def test_low_stock_products_are_listed_by_filament_line_then_not_in_the_catalog(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    scan(client, token, SyntheticTag(color_rgba="F5F5F0FF"), "received")
    scan(client, token, SyntheticTag(color_rgba="FF0000FF"), "received")
    names = [p.display_name for p in db.query(Product).order_by(Product.id)]
    _jade_white_in_the_catalog(db)
    jade = _product(db, names[0], threshold=2, color=JADE)
    red = _product(db, names[1], threshold=1)

    body = viewer.get(LIST).json()

    [line] = body["lines"]
    assert line["name"] == "PLA Basic"
    assert line["to_buy"] == 2
    [item] = line["items"]
    assert item["product"]["id"] == jade.id
    assert item["product"]["catalog_link"]["bambu_code"] == "10100"
    assert item["to_buy"] == 2
    assert item["reasons"] == [{"kind": "low_stock", "spools": 2, "sealed": 1, "threshold": 2}]
    [other] = body["not_in_catalog"]
    assert other["product"]["id"] == red.id
    assert other["product"]["filament_type"] == "PLA"
    assert other["to_buy"] == 1
