"""Manual catalog links, through the product update (Editor and up): set, cleared, kept by
every sync, moved along OFDB's merges, and kept when their color leaves the catalog."""

from typing import Any

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, changed_export, gz, ok, refresh, variant

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

BLACK = SyntheticTag(variant_id="A00-K0")


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR, username="frank")


@pytest.fixture
def product_id(client: TestClient, token: str) -> int:
    """A scanned PLA Basic Black, linked from its tag by the sync."""
    scan(client, token, BLACK, "received")
    refresh(client)
    return client.get("/api/v1/products", headers=admin()).json()[0]["id"]


def _link(client: TestClient, product_id: int, color: str | None) -> Any:
    return client.patch(
        f"/api/v1/products/{product_id}", json={"catalog_color": color}, headers=CSRF
    )


def _read(client: TestClient, product_id: int) -> dict[str, Any]:
    return client.get(f"/api/v1/products/{product_id}", headers=admin()).json()["product"][
        "catalog_link"
    ]


def test_an_editor_links_a_product_by_hand(editor: TestClient, product_id: int) -> None:
    response = _link(editor, product_id, "var-jade")

    assert response.status_code == 200, response.text
    link = response.json()["catalog_link"]
    assert link["uuid"] == "var-jade"
    assert link["name"] == "Jade White"
    assert link["line"] == "PLA Basic"
    assert link["bambu_code"] is None  # Jade White's sizes carry no article number
    assert link["how"] == "hand"
    assert link["in_catalog"] is True
    assert link["linked_by"] == "frank"
    assert link["linked_at"] is not None
    assert link["tag_link_exists"] is True
    assert _read(editor, product_id) == link


def test_setting_the_same_color_again_refreshes_who_and_when(
    app: FastAPI, editor: TestClient, product_id: int
) -> None:
    first = _link(editor, product_id, "var-jade").json()["catalog_link"]

    again = _link(signed_in(app, Role.ADMIN, username="sam"), product_id, "var-jade").json()

    assert again["catalog_link"]["linked_by"] == "sam"
    assert again["catalog_link"]["linked_at"] >= first["linked_at"]


def test_clearing_goes_back_to_the_color_from_its_tag(editor: TestClient, product_id: int) -> None:
    _link(editor, product_id, "var-jade")

    cleared = _link(editor, product_id, None).json()["catalog_link"]

    assert cleared["uuid"] == "var-black"
    assert cleared["how"] == "tag"
    assert cleared["linked_by"] is None


def test_clearing_a_product_without_a_tag_link_leaves_none(
    client: TestClient, editor: TestClient
) -> None:
    refresh(client)
    made = editor.post(
        "/api/v1/products",
        json={"display_name": "By hand", "filament_type": "PLA", "color_rgba": "FFFFFFFF"},
        headers=CSRF,
    ).json()
    linked = _link(editor, made["id"], "var-jade").json()["catalog_link"]
    assert linked["tag_link_exists"] is False

    assert _link(editor, made["id"], None).json()["catalog_link"] is None


def test_leaving_catalog_color_out_changes_nothing(editor: TestClient, product_id: int) -> None:
    _link(editor, product_id, "var-jade")

    response = editor.patch(
        f"/api/v1/products/{product_id}", json={"display_name": "Jade"}, headers=CSRF
    )

    assert response.json()["catalog_link"]["uuid"] == "var-jade"


def test_an_unknown_color_is_refused(editor: TestClient, product_id: int) -> None:
    response = _link(editor, product_id, "no-such-uuid")

    assert response.status_code == 422
    assert _read(editor, product_id)["how"] == "tag"


@pytest.mark.parametrize("value", ["", "x" * 37, 5])
def test_a_malformed_color_is_refused(editor: TestClient, product_id: int, value: Any) -> None:
    assert _link(editor, product_id, value).status_code == 422


def test_a_viewer_cannot_link(app: FastAPI, client: TestClient, product_id: int) -> None:
    viewer = signed_in(app, Role.VIEWER)

    assert _link(viewer, product_id, "var-jade").status_code == 403
    assert _read(client, product_id)["how"] == "tag"


def test_a_sync_never_replaces_a_manual_link(
    client: TestClient, editor: TestClient, product_id: int
) -> None:
    _link(editor, product_id, "var-jade")

    refresh(client)

    link = _read(client, product_id)
    assert link["uuid"] == "var-jade"
    assert link["linked_by"] == "frank"


def test_a_manual_link_follows_an_ofdb_merge(
    client: TestClient, editor: TestClient, product_id: int, ofdb: FakeSource
) -> None:
    linked = _link(editor, product_id, "var-jade").json()["catalog_link"]
    merged = changed_export()
    merged["variants"].append(
        variant("var-white", "White", "#FFFFFF", "id-fil-pla-basic", moved_from=["var-jade"])
    )
    ofdb.serve(ok(gz(merged), etag='"v2"'))

    refresh(client)

    link = _read(client, product_id)
    assert link["uuid"] == "var-white"
    assert link["name"] == "White"
    assert link["how"] == "hand"
    assert (link["linked_by"], link["linked_at"]) == (linked["linked_by"], linked["linked_at"])


def test_a_manual_link_to_a_dropped_color_is_kept(
    client: TestClient, editor: TestClient, product_id: int, ofdb: FakeSource
) -> None:
    _link(editor, product_id, "var-jade")
    ofdb.serve(ok(gz(changed_export()), etag='"v2"'))  # Jade White is gone

    refresh(client)

    link = _read(client, product_id)
    assert link["in_catalog"] is False
    assert (link["uuid"], link["name"], link["line"], link["hexes"]) == (None,) * 4
    assert (link["was_line"], link["was_name"]) == ("PLA Basic", "Jade White")
    assert link["how"] == "hand"
    # It does not fall back to the tag's color: the person chose it.
    assert link["tag_link_exists"] is True


def test_clearing_a_link_to_a_dropped_color_goes_back_to_the_color_from_its_tag(
    client: TestClient, editor: TestClient, product_id: int, ofdb: FakeSource
) -> None:
    _link(editor, product_id, "var-jade")
    ofdb.serve(ok(gz(changed_export()), etag='"v2"'))  # Jade White is gone
    refresh(client)

    cleared = _link(editor, product_id, None).json()["catalog_link"]

    assert cleared["uuid"] == "var-black"
    assert cleared["how"] == "tag"
    assert cleared["in_catalog"] is True
    assert cleared["linked_by"] is None
