"""Owned catalog colors and Bambu codes in the catalog read: a color is owned when a product
linked to it has a Sealed or Open spool. Linked products are kept out of their own color's
similar in-stock colors."""

from typing import Any

import pytest
from api_helpers import admin, scan
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, changed_export, gz, ok, refresh

from filament_tracker.decoder.synthetic import SyntheticTag

CATALOG = "/api/v1/catalog"


def colors(client: TestClient) -> dict[str, dict[str, Any]]:
    body = client.get(CATALOG, headers=admin()).json()
    return {c["name"]: c for line in body["lines"] for c in line["colors"]}


def by_hand(client: TestClient, name: str, rgba: str, color: str, *actions: str) -> int:
    """A product added by hand and linked by hand to `color`, with one manual spool taken
    through `actions` after it is received."""
    made = client.post(
        "/api/v1/products",
        json={"display_name": name, "filament_type": "PLA", "color_rgba": rgba},
        headers=admin(),
    ).json()
    client.patch(
        f"/api/v1/products/{made['id']}", json={"catalog_color": color}, headers=admin()
    ).raise_for_status()
    spool = client.post("/api/v1/spools", json={"product_id": made["id"]}, headers=admin()).json()
    for action in actions:
        client.post(
            f"/api/v1/spools/{spool['id']}/events", json={"action": action}, headers=admin()
        ).raise_for_status()
    return made["id"]


@pytest.fixture
def shelf(client: TestClient, token: str) -> dict[str, int]:
    """Scanned PLA Basic Black (sealed, linked from its tag); a hand-added "Black PLA"
    linked by hand to Black (open); "Jade PLA" linked to Jade White and used up; and an
    unlinked black PETG (open)."""
    refresh(client)
    scan(client, token, SyntheticTag(variant_id="A00-K0"), "received")
    petg = SyntheticTag(
        filament_type="PETG",
        detailed_filament_type="PETG HF",
        material_id="GFG00",
        variant_id="G00-K0",
        color_rgba="000000FF",
    )
    scan(client, token, petg, "received")
    scan(client, token, petg, "opened")
    ids = {
        p["display_name"]: p["id"] for p in client.get("/api/v1/products", headers=admin()).json()
    }
    ids["Black PLA"] = by_hand(client, "Black PLA", "050505FF", "var-black", "opened")
    ids["Jade PLA"] = by_hand(client, "Jade PLA", "FFFFFFFF", "var-jade", "opened", "empty")
    return ids


def test_a_color_shows_its_bambu_code(client: TestClient) -> None:
    refresh(client)

    found = colors(client)

    assert found["Black"]["bambu_code"] == "10101"
    assert found["Jade White"]["bambu_code"] is None


def test_a_color_with_in_stock_linked_products_is_owned_with_each_listed(
    client: TestClient, shelf: dict[str, int]
) -> None:
    black = colors(client)["Black"]

    assert black["owned"] is True
    assert black["owned_products"] == [
        {
            "product_id": shelf["Black PLA"],
            "name": "Black PLA",
            "hex": "050505",
            "material": "PLA",
            "how": "hand",
            "sealed": 0,
            "open": 1,
        },
        {
            "product_id": shelf["PLA Basic #000000"],
            "name": "PLA Basic #000000",
            "hex": "000000",
            "material": "PLA",
            "how": "tag",
            "sealed": 1,
            "open": 0,
        },
    ]
    assert black["linked_none_in_stock"] == []


def test_linked_products_are_not_similar_colors_of_their_own_color(
    client: TestClient, shelf: dict[str, int]
) -> None:
    similar = colors(client)["Black"]["similar"]

    # Only the unlinked black PETG is offered as a substitute.
    assert [(m["name"], m["material"]) for m in similar] == [("PETG HF #000000", "PETG")]


def test_a_linked_product_with_none_in_stock_does_not_make_its_color_owned(
    client: TestClient, shelf: dict[str, int]
) -> None:
    jade = colors(client)["Jade White"]

    assert jade["owned"] is False
    assert jade["owned_products"] == []
    assert jade["linked_none_in_stock"] == [{"product_id": shelf["Jade PLA"], "name": "Jade PLA"}]


def test_unlinked_colors_are_not_owned(client: TestClient, shelf: dict[str, int]) -> None:
    cream = colors(client)["Cream"]

    assert (cream["owned"], cream["owned_products"], cream["linked_none_in_stock"]) == (
        False,
        [],
        [],
    )


def test_a_multi_color_color_can_be_owned(client: TestClient) -> None:
    refresh(client)
    by_hand(client, "Whisper", "9CDBD9FF", "var-gradient")

    gradient = colors(client)["Arctic Whisper"]

    assert gradient["owned"] is True
    assert [p["name"] for p in gradient["owned_products"]] == ["Whisper"]


def test_a_link_to_a_dropped_color_counts_nowhere(client: TestClient, ofdb: FakeSource) -> None:
    refresh(client)
    by_hand(client, "Jade PLA", "FFFFFFFF", "var-jade")
    ofdb.serve(ok(gz(changed_export()), etag='"v2"'))  # Jade White is gone

    refresh(client)

    found = colors(client)
    assert not [c for c in found.values() if c["owned"] or c["linked_none_in_stock"]]
