"""Similar in-stock colors in the catalog read, and the similarity cutoff setting."""

from typing import Any

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import refresh

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

CATALOG = "/api/v1/catalog"
SETTINGS = "/api/v1/settings/catalog"


def colors(client: TestClient) -> dict[str, dict[str, Any]]:
    """The catalog's colors by name."""
    body = client.get(CATALOG, headers=admin()).json()
    return {c["name"]: c for line in body["lines"] for c in line["colors"]}


def matches(client: TestClient, name: str) -> list[tuple[str, str, float, int, int, bool]]:
    return [
        (m["hex"], m["material"], m["delta_e"], m["sealed"], m["open"], m["different_material"])
        for m in colors(client)[name]["similar"]
    ]


def stock(client: TestClient, token: str, rgba: str, material: str, *actions: str) -> None:
    """One spool of a product, scanned through `actions` (received, opened, empty)."""
    # A product is its material ID, variant ID and color, so each material gets its own IDs.
    tag = SyntheticTag(
        color_rgba=rgba,
        filament_type=material,
        detailed_filament_type=material,
        material_id=f"GF{material[:3]}",
        variant_id=f"{material[:3]}-{rgba[:2]}",
    )
    for action in actions:
        scan(client, token, tag, action)


def set_cutoff(client: TestClient, value: str) -> Any:
    return client.put(SETTINGS, json={"values": {"similarity_cutoff": value}}, headers=admin())


@pytest.fixture
def shelf(client: TestClient, token: str) -> None:
    """Black PLA (1 sealed, 1 open), black PETG (open), near-black PLA-CF (sealed), white
    PLA that is used up, and red PLA far from everything."""
    stock(client, token, "000000FF", "PLA", "received")
    stock(client, token, "000000FF", "PLA", "received", "opened")
    stock(client, token, "000000FF", "PETG", "received", "opened")
    stock(client, token, "0A0A0AFF", "PLA-CF", "received")
    stock(client, token, "FFFFFFFF", "PLA", "received", "opened", "empty")
    stock(client, token, "C12E1FFF", "PLA", "received")
    refresh(client)


def test_lists_in_stock_products_within_the_cutoff_closest_first(
    client: TestClient, shelf: None
) -> None:
    assert matches(client, "Black") == [
        ("000000", "PLA", 0.0, 1, 1, False),
        ("000000", "PETG", 0.0, 0, 1, True),
        ("0A0A0A", "PLA-CF", 1.6, 1, 0, True),
    ]


def test_each_match_names_its_product(client: TestClient, shelf: None) -> None:
    products = {p["id"]: p for p in client.get("/api/v1/products", headers=admin()).json()}

    for match in colors(client)["Black"]["similar"]:
        product = products[match["product_id"]]
        assert match["name"] == product["display_name"]
        assert match["hex"] == product["color_rgba"][:6]


def test_a_used_up_product_is_not_similar_in_stock(client: TestClient, shelf: None) -> None:
    assert matches(client, "Jade White") == []


def test_a_provisional_product_counts_with_the_color_it_was_entered_with(
    client: TestClient, shelf: None
) -> None:
    product = client.post(
        "/api/v1/products",
        json={"display_name": "Mystery white", "filament_type": "pla", "color_rgba": "FEFEFEFF"},
        headers=admin(),
    ).json()
    client.post("/api/v1/spools", json={"product_id": product["id"]}, headers=admin())

    ((hex_, material, delta_e, sealed, open_, different),) = matches(client, "Jade White")

    assert (hex_, material, sealed, open_) == ("FEFEFE", "pla", 1, 0)
    assert delta_e < 1
    # The material is compared ignoring case.
    assert different is False


def test_multi_color_catalog_colors_get_no_matches(client: TestClient, shelf: None) -> None:
    gradient = colors(client)["Arctic Whisper"]

    assert gradient["multi_color"] is True
    assert gradient["similar"] == []


def test_the_read_says_which_cutoff_it_used(client: TestClient, shelf: None) -> None:
    assert client.get(CATALOG, headers=admin()).json()["cutoff"] == 10


def test_a_new_cutoff_applies_at_once(client: TestClient, shelf: None) -> None:
    response = set_cutoff(client, "1.5")

    assert response.status_code == 200, response.text
    assert client.get(CATALOG, headers=admin()).json()["cutoff"] == 1.5
    assert [m[1] for m in matches(client, "Black")] == ["PLA", "PETG"]


@pytest.mark.parametrize("value", ["0.4", "50.5", "-1", "ten", ""])
def test_a_cutoff_outside_its_range_is_refused(client: TestClient, value: str) -> None:
    response = set_cutoff(client, value)

    assert response.status_code == 422
    assert "similarity_cutoff" in response.json()["detail"]["problems"]
    assert client.get(CATALOG, headers=admin()).json()["cutoff"] == 10


@pytest.mark.parametrize("value", ["0.5", "50"])
def test_the_cutoff_range_includes_its_ends(client: TestClient, value: str) -> None:
    assert set_cutoff(client, value).status_code == 200


def test_the_catalog_settings_default_to_daily_and_10(client: TestClient) -> None:
    body = client.get(SETTINGS, headers=admin()).json()

    settings = {s["key"]: s for s in body["settings"]}
    assert settings["catalog_sync"]["value"] == "daily"
    assert settings["similarity_cutoff"]["value"] == "10.0"
    assert {s["source"] for s in settings.values()} == {"default"}


@pytest.mark.parametrize("role", [Role.VIEWER, Role.EDITOR])
def test_only_admins_see_or_change_the_catalog_settings(
    app: FastAPI, client: TestClient, role: Role
) -> None:
    user = signed_in(app, role)

    assert user.get(SETTINGS).status_code == 403
    response = user.put(SETTINGS, json={"values": {"similarity_cutoff": "5"}}, headers=CSRF)
    assert response.status_code == 403
