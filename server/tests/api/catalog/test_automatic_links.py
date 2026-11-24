"""Automatic catalog links, through the API: a product's tag IDs find its entry in
BambuStudio's list, whose Bambu code finds its catalog color. Worked out after every sync
and when a scan creates a product or fills in a provisional one."""

from typing import Any

from api_helpers import admin, scan
from bambustudio_fake import body, color_codes, entry
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, export, gz, ok, refresh, status
from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.decoder.synthetic import SyntheticTag

PRODUCTS = "/api/v1/products"
# PLA Basic Black as BambuStudio lists it: GFA00 and K0.
BLACK = SyntheticTag(variant_id="A00-K0")

FROM_TAG = {
    "uuid": "var-black",
    "name": "Black",
    "line": "PLA Basic",
    "hexes": ["000000"],
    "bambu_code": "10101",
    "how": "tag",
    "in_catalog": True,
    "linked_by": None,
    "linked_at": None,
    "was_line": None,
    "was_name": None,
    "tag_link_exists": True,
}


def links(client: TestClient) -> dict[str, Any]:
    """Each product's catalog link, by display name."""
    return {
        p["display_name"]: p["catalog_link"] for p in client.get(PRODUCTS, headers=admin()).json()
    }


def test_a_sync_links_a_scanned_product_from_its_tag(client: TestClient, token: str) -> None:
    scan(client, token, BLACK, "received")
    assert list(links(client).values()) == [None]

    refresh(client)

    assert list(links(client).values()) == [FROM_TAG]


def test_the_link_shows_on_every_product_read(client: TestClient, token: str) -> None:
    refresh(client)
    scan(client, token, BLACK, "received")

    spool = client.get("/api/v1/spools", headers=admin()).json()["items"][0]
    inventory = client.get("/api/v1/inventory", headers=admin()).json()[0]
    assert spool["product"]["catalog_link"] == FROM_TAG
    assert inventory["product"]["catalog_link"] == FROM_TAG


def test_a_scan_links_the_product_it_creates(client: TestClient, token: str) -> None:
    refresh(client)

    scan(client, token, BLACK, "received")

    assert list(links(client).values()) == [FROM_TAG]


def test_a_scan_links_the_provisional_product_it_fills_in(client: TestClient, token: str) -> None:
    refresh(client)
    made = client.post(
        PRODUCTS,
        json={"display_name": "My black", "filament_type": "PLA", "color_rgba": "000000FF"},
        headers=admin(),
    ).json()
    client.post(
        "/api/v1/spools", json={"product_id": made["id"]}, headers=admin()
    ).raise_for_status()
    assert links(client) == {"My black": None}

    scan(client, token, BLACK, "received")

    assert links(client) == {"My black": FROM_TAG}


def test_no_link_without_an_exact_entry(client: TestClient, token: str) -> None:
    # The tag reads K00 where BambuStudio lists K0: no guessing.
    scan(client, token, SyntheticTag(), "received")
    # A00-Z9 is listed, but its Bambu code is no catalog color's.
    scan(client, token, SyntheticTag(variant_id="A00-Z9", color_rgba="111111FF"), "received")

    refresh(client)

    assert list(links(client).values()) == [None, None]


def test_no_link_when_two_entries_match(
    client: TestClient, token: str, bambustudio: FakeSource
) -> None:
    bambustudio.serve(
        ok(body(color_codes(entry("10101", "GFA00", "K0"), entry("10102", "GFA00", "K0"))))
    )
    scan(client, token, BLACK, "received")

    refresh(client)

    assert list(links(client).values()) == [None]


def test_no_link_when_the_code_belongs_to_two_catalog_colors(
    client: TestClient, token: str, ofdb: FakeSource
) -> None:
    data = export()
    data["sizes"].append(_size("size-jade", "id-var-jade", "10101"))
    ofdb.serve(ok(gz(data)))
    scan(client, token, BLACK, "received")

    refresh(client)

    assert list(links(client).values()) == [None]


def test_a_color_whose_sizes_disagree_has_no_code_and_no_link(
    client: TestClient, token: str, ofdb: FakeSource
) -> None:
    data = export()
    data["sizes"][1]["article_number"] = "10199"  # the spool says 10199, the refill 10101
    ofdb.serve(ok(gz(data)))
    scan(client, token, BLACK, "received")

    refresh(client)

    assert list(links(client).values()) == [None]


def test_provisional_products_get_no_link(client: TestClient, db: Session) -> None:
    refresh(client)
    client.post(
        PRODUCTS,
        json={"display_name": "By hand", "filament_type": "PLA", "color_rgba": "000000FF"},
        headers=admin(),
    ).raise_for_status()
    # The AMS makes a product with a material ID and no variant ID.
    db.add(
        Product(
            material_id="GFA00",
            filament_type="PLA",
            color_rgba="000000FF",
            display_name="From the AMS",
            provisional=True,
            from_ams=True,
        )
    )
    db.commit()

    refresh(client)

    assert links(client) == {"By hand": None, "From the AMS": None}


def test_a_later_sync_that_changes_the_data_changes_the_link(
    client: TestClient, token: str, bambustudio: FakeSource
) -> None:
    scan(client, token, BLACK, "received")
    refresh(client)
    bambustudio.serve(ok(body(color_codes(entry("99999", "GFA00", "K0"))), etag='"bs-v2"'))

    refresh(client)

    assert list(links(client).values()) == [None]


def test_links_are_worked_out_whatever_each_source_did(
    client: TestClient, token: str, ofdb: FakeSource, bambustudio: FakeSource
) -> None:
    # An upgraded install: the catalog is there, the product was scanned before links
    # existed, and this run both sources fail.
    refresh(client)
    scan(client, token, BLACK, "received")
    ofdb.serve(status(500))
    bambustudio.serve(status(500))

    refresh(client)

    assert list(links(client).values()) == [FROM_TAG]


def test_a_changed_link_makes_no_review_item_or_event(client: TestClient, token: str) -> None:
    scan(client, token, BLACK, "received")
    events = client.get("/api/v1/events", headers=admin()).json()["total"]

    refresh(client)

    assert client.get("/api/v1/events", headers=admin()).json()["total"] == events
    review = client.get("/api/v1/review", headers=admin()).json()
    assert review["flagged_events"] == review["unidentified_tags"] == review["likely_empty"] == []


def _size(uuid: str, variant_id: str, code: str) -> dict[str, Any]:
    return {
        "uuid": uuid,
        "id": f"id-{uuid}",
        "variant_id": variant_id,
        "filament_weight": 1000,
        "article_number": code,
        "discontinued": False,
    }


# --- Catalog names -----------------------------------------------------------------------


def _names(client: TestClient) -> list[str]:
    return [p["display_name"] for p in client.get(PRODUCTS, headers=admin()).json()]


def test_a_scan_that_creates_and_links_a_product_gives_it_the_catalog_name(
    client: TestClient, token: str
) -> None:
    refresh(client)

    result = scan(client, token, BLACK, "received")

    assert result["product"]["display_name"] == "Black PLA Basic"
    assert _names(client) == ["Black PLA Basic"]
