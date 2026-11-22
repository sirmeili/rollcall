"""The first scan of a color on the shopping list, through the scan route: when the tag's
IDs give a BambuStudio entry, whose Bambu code gives one catalog color, the one "From
the catalog" product linked to that color is filled in rather than a new product made."""

from typing import Any

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import refresh

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

PRODUCTS = "/api/v1/products"
HAND = "/api/v1/shopping-list/hand-reasons"
# PLA Basic Black as BambuStudio lists it (GFA00 and K0), whose Bambu code is var-black's.
BLACK = SyntheticTag(variant_id="A00-K0")


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    refresh(client)
    return signed_in(app, Role.EDITOR, username="frank")


def _from_the_catalog(editor: TestClient, color: str, spools: int = 1) -> dict[str, Any]:
    """Put a catalog color with no product on the list by hand; the product made for it."""
    response = editor.post(HAND, json={"catalog_color": color, "spools": spools}, headers=CSRF)
    assert response.status_code == 200, response.text
    body = response.json()
    [item] = [i for line in body["lines"] for i in line["items"]]
    return item


def _products(client: TestClient) -> list[dict[str, Any]]:
    return client.get(PRODUCTS, headers=admin()).json()


def test_the_first_scan_fills_in_the_from_the_catalog_product(
    client: TestClient, token: str, editor: TestClient
) -> None:
    item = _from_the_catalog(editor, "var-black", spools=2)
    made = item["product"]["id"]
    assert editor.patch(
        f"{PRODUCTS}/{made}", json={"low_stock_threshold": 3}, headers=CSRF
    ).is_success

    result = scan(client, token, BLACK, "received")

    assert result["product"]["id"] == made
    [product] = _products(client)
    assert product["id"] == made
    assert (product["material_id"], product["variant_id"]) == ("GFA00", "A00-K0")
    assert (product["provisional"], product["from_catalog"]) == (False, False)
    assert product["low_stock_threshold"] == 3
    link = product["catalog_link"]
    assert (link["uuid"], link["how"], link["linked_by"]) == ("var-black", "hand", "frank")
    [spool] = client.get("/api/v1/spools", headers=admin()).json()["items"]
    assert spool["product"]["id"] == made
    [kept] = [
        i
        for line in editor.get("/api/v1/shopping-list").json()["lines"]
        for i in line["items"]
        if i["product"]["id"] == made
    ]
    assert [(r["kind"], r["spools"]) for r in kept["reasons"] if r["kind"] == "hand"] == [
        ("hand", 2)
    ]
    assert [e["action"] for e in kept["shopping_history"]] == ["added_by_hand"]


def test_a_lookup_reports_the_product_the_scan_would_fill_in(
    client: TestClient, token: str, editor: TestClient
) -> None:
    made = _from_the_catalog(editor, "var-black")["product"]["id"]

    result = scan(client, token, BLACK, "lookup")

    assert result["product"]["id"] == made
    [product] = _products(client)
    assert (product["provisional"], product["from_catalog"]) == (True, True)


@pytest.mark.parametrize(
    "tag",
    [
        # The tag reads K00 where BambuStudio lists K0: the chain doesn't resolve.
        SyntheticTag(),
        # A00-Z9 is listed, but its Bambu code is no catalog color's.
        SyntheticTag(variant_id="A00-Z9"),
    ],
)
def test_a_tag_whose_chain_does_not_resolve_makes_a_new_product(
    client: TestClient, token: str, editor: TestClient, tag: SyntheticTag
) -> None:
    made = _from_the_catalog(editor, "var-black")["product"]["id"]

    result = scan(client, token, tag, "received")

    assert result["product"]["id"] != made
    [waiting] = [p for p in _products(client) if p["id"] == made]
    assert (waiting["provisional"], waiting["from_catalog"]) == (True, True)


def test_a_color_no_provisional_product_is_linked_to_makes_a_new_product(
    client: TestClient, token: str, editor: TestClient
) -> None:
    jade = _from_the_catalog(editor, "var-jade")["product"]["id"]

    result = scan(client, token, BLACK, "received")

    assert result["product"]["id"] != jade
    new = result["product"]["id"]
    [scanned] = [p for p in _products(client) if p["id"] == new]
    assert (scanned["provisional"], scanned["catalog_link"]["uuid"]) == (False, "var-black")
    [waiting] = [p for p in _products(client) if p["id"] == jade]
    assert (waiting["provisional"], waiting["from_catalog"]) == (True, True)


def test_a_product_already_filled_in_and_linked_to_the_color_is_not_filled_in_again(
    client: TestClient, token: str, editor: TestClient
) -> None:
    # A product scanned from a K00 tag, linked to Black by hand.
    other = scan(client, token, SyntheticTag(), "received")["product"]["id"]
    assert editor.patch(
        f"{PRODUCTS}/{other}", json={"catalog_color": "var-black"}, headers=CSRF
    ).is_success

    result = scan(client, token, BLACK, "received")

    assert result["product"]["id"] != other
    assert len(_products(client)) == 2


def test_a_provisional_product_made_by_hand_and_linked_to_the_color_is_not_filled_in(
    client: TestClient, token: str, editor: TestClient
) -> None:
    made = editor.post(
        PRODUCTS,
        json={"display_name": "Black PLA", "filament_type": "PLA", "color_rgba": "050505FF"},
        headers=CSRF,
    ).json()["id"]
    assert editor.patch(
        f"{PRODUCTS}/{made}", json={"catalog_color": "var-black"}, headers=CSRF
    ).is_success

    result = scan(client, token, BLACK, "received")

    assert result["product"]["id"] != made
    [waiting] = [p for p in _products(client) if p["id"] == made]
    assert waiting["provisional"] is True
