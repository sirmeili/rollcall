"""Adding to the shopping list by hand over the API: products and catalog colors, removing a
hand reason, the item's history, and the "From the catalog" product on Products."""

import pytest
from api_helpers import CSRF, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_shopping_list import JADE, LIST, _jade_white_in_the_catalog

from filament_tracker.db.models import Product
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

HAND = f"{LIST}/hand-reasons"


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR, username="frank")


def _black(db: Session) -> Product:
    black = Product(
        filament_type="PLA", color_rgba="000000FF", display_name="Black", provisional=True
    )
    db.add(black)
    db.commit()
    return black


def _items(body: dict) -> list[dict]:
    return [i for line in body["lines"] for i in line["items"]] + body["not_in_catalog"]


def test_a_product_added_by_hand_is_on_the_list_with_its_reason_and_history(
    editor: TestClient, db: Session
) -> None:
    black = _black(db)

    response = editor.post(HAND, json={"product_id": black.id, "spools": 2}, headers=CSRF)

    assert response.status_code == 200
    [item] = _items(response.json())
    assert item["product"]["id"] == black.id
    assert item["to_buy"] == 2
    [reason] = item["reasons"]
    assert (reason["kind"], reason["spools"], reason["by"]) == ("hand", 2, "frank")
    [entry] = item["shopping_history"]
    assert (entry["action"], entry["spools"], entry["on_order"], entry["by"]) == (
        "added_by_hand",
        2,
        0,
        "frank",
    )
    assert _items(editor.get(LIST).json()) == [item]


def test_adding_a_product_already_on_the_list_adds_a_reason_not_an_item(
    editor: TestClient, db: Session
) -> None:
    black = _black(db)
    editor.post(HAND, json={"product_id": black.id, "spools": 2}, headers=CSRF)

    body = editor.post(HAND, json={"product_id": black.id, "spools": 1}, headers=CSRF).json()

    [item] = _items(body)
    assert item["to_buy"] == 3
    assert [r["spools"] for r in item["reasons"]] == [2, 1]


def test_a_catalog_color_with_no_product_gets_a_from_the_catalog_one(
    editor: TestClient, db: Session
) -> None:
    _jade_white_in_the_catalog(db)

    body = editor.post(HAND, json={"catalog_color": JADE, "spools": 1}, headers=CSRF).json()

    [line] = body["lines"]
    [item] = line["items"]
    made = item["product"]
    assert made["display_name"] == "Jade White PLA Basic"
    assert (made["provisional"], made["from_catalog"], made["from_ams"]) == (True, True, False)
    link = made["catalog_link"]
    assert (link["uuid"], link["how"], link["linked_by"]) == (JADE, "hand", "frank")
    [listed] = [p for p in editor.get("/api/v1/products").json() if p["id"] == made["id"]]
    assert listed["from_catalog"] is True


def test_a_catalog_color_already_linked_reuses_its_product(editor: TestClient, db: Session) -> None:
    _jade_white_in_the_catalog(db)
    black = _black(db)
    black.catalog_manual_uuid = JADE
    db.commit()

    body = editor.post(HAND, json={"catalog_color": JADE, "spools": 1}, headers=CSRF).json()

    [item] = _items(body)
    assert item["product"]["id"] == black.id
    assert db.query(Product).count() == 1


def test_a_hand_reason_can_be_removed_and_the_removal_is_in_the_history(
    editor: TestClient, db: Session
) -> None:
    black = _black(db)
    editor.post(HAND, json={"product_id": black.id, "spools": 2}, headers=CSRF)
    body = editor.post(HAND, json={"product_id": black.id, "spools": 1}, headers=CSRF).json()
    first = _items(body)[0]["reasons"][0]["id"]

    response = editor.delete(f"{HAND}/{first}", headers=CSRF)

    assert response.status_code == 200
    [item] = _items(response.json())
    assert [r["spools"] for r in item["reasons"]] == [1]
    assert [(e["action"], e["spools"]) for e in item["shopping_history"]] == [
        ("removed_by_hand", 2),
        ("added_by_hand", 1),
        ("added_by_hand", 2),
    ]
    assert editor.delete(f"{HAND}/{first}", headers=CSRF).status_code == 404


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"spools": 1}, 422),
        ({"product_id": 1, "catalog_color": JADE, "spools": 1}, 422),
        ({"product_id": 1, "spools": 0}, 422),
        ({"product_id": 1, "spools": 1000}, 422),
        ({"product_id": 999, "spools": 1}, 404),
        ({"catalog_color": "no-such-color", "spools": 1}, 422),
    ],
)
def test_a_bad_addition_is_refused(
    editor: TestClient, db: Session, body: dict, status: int
) -> None:
    _black(db)

    assert editor.post(HAND, json=body, headers=CSRF).status_code == status
    assert _items(editor.get(LIST).json()) == []


def test_a_from_the_catalog_product_stops_being_one_once_a_tag_fills_it_in(
    client: TestClient, token: str, editor: TestClient, db: Session
) -> None:
    _jade_white_in_the_catalog(db)
    body = editor.post(HAND, json={"catalog_color": JADE, "spools": 1}, headers=CSRF).json()
    made = body["lines"][0]["items"][0]["product"]["id"]
    # A spool of it added by hand, then its tag scanned: the scan fills the product in.
    assert editor.post("/api/v1/spools", json={"product_id": made}, headers=CSRF).is_success

    scan(client, token, SyntheticTag(color_rgba="F5F5F0FF"), "opened")

    [listed] = [p for p in editor.get("/api/v1/products").json() if p["id"] == made]
    assert (listed["provisional"], listed["from_catalog"]) == (False, False)
    assert listed["catalog_link"]["how"] == "hand"
