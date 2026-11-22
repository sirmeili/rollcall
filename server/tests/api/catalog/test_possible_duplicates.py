"""Possible duplicates in Review, through the scan and Review routes: a scan whose tag's chain
gives no catalog color makes a new product, and Review asks whether it is the same as a "From
the catalog" product of the same filament line with a close color."""

from typing import Any

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import refresh
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.shopping_models import ShoppingHistory
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

PRODUCTS = "/api/v1/products"
HAND = "/api/v1/shopping-list/hand-reasons"
REVIEW = "/api/v1/review"
# PLA Basic Black read as K00, where BambuStudio lists K0: the chain gives no catalog color,
# but GFA00's Bambu codes give the PLA Basic line.
UNSURE = SyntheticTag()
# Near black, within the default cutoff of Black (ΔE about 2).
NEAR_BLACK = SyntheticTag(color_rgba="050505FF")


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    refresh(client)
    return signed_in(app, Role.EDITOR, username="frank")


def _from_the_catalog(editor: TestClient, color: str, spools: int = 1) -> int:
    """Put a catalog color with no product on the list by hand; the id of the product made."""
    response = editor.post(HAND, json={"catalog_color": color, "spools": spools}, headers=CSRF)
    assert response.status_code == 200, response.text
    items = [i for line in response.json()["lines"] for i in line["items"]]
    [made] = [i["product"]["id"] for i in items if i["product"]["catalog_link"]["uuid"] == color]
    return made


def _duplicates(client: TestClient) -> list[dict[str, Any]]:
    return client.get(REVIEW, headers=admin()).json()["possible_duplicates"]


def test_a_scan_the_chain_cannot_place_puts_a_possible_duplicate_in_review(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")

    scanned = scan(client, token, NEAR_BLACK, "received")["product"]["id"]

    assert scanned != black
    [duplicate] = _duplicates(client)
    assert duplicate["product"]["id"] == scanned
    assert [c["id"] for c in duplicate["candidates"]] == [black]
    assert duplicate["candidates"][0]["catalog_link"]["uuid"] == "var-black"


def _item(client: TestClient, product_id: int) -> dict[str, Any]:
    body = client.get("/api/v1/shopping-list", headers=admin()).json()
    items = [i for line in body["lines"] for i in line["items"]] + body["not_in_catalog"]
    [found] = [i for i in items + body["dismissed"] if i["product"]["id"] == product_id]
    return found


def _same(client: TestClient, duplicate: dict[str, Any], candidate: int) -> Any:
    return client.post(
        f"{REVIEW}/duplicates/{duplicate['id']}/same-product",
        json={"candidate_id": candidate},
        headers=CSRF,
    )


def _post(client: TestClient, duplicate: dict[str, Any], action: str) -> Any:
    return client.post(f"{REVIEW}/duplicates/{duplicate['id']}/{action}", headers=CSRF)


@pytest.mark.parametrize(
    ("color", "tag"),
    [
        # Beyond the cutoff: grey is nowhere near Black.
        ("var-black", SyntheticTag(color_rgba="808080FF")),
        # Another filament line: PETG HF Cream matches, but GFA00's codes give PLA Basic only.
        ("var-cream", SyntheticTag(color_rgba="F3E0B8FF")),
        # The chain gives Black, a different catalog color from the close Jade White.
        ("var-jade", SyntheticTag(variant_id="A00-K0", color_rgba="FFFFFFFF")),
    ],
)
def test_no_possible_duplicate_without_a_close_candidate_of_the_same_line(
    client: TestClient, token: str, editor: TestClient, color: str, tag: SyntheticTag
) -> None:
    _from_the_catalog(editor, color)

    scan(client, token, tag, "received")

    assert _duplicates(client) == []


def test_a_lookup_puts_nothing_in_review(
    client: TestClient, token: str, editor: TestClient
) -> None:
    _from_the_catalog(editor, "var-black")

    scan(client, token, NEAR_BLACK, "lookup")

    assert _duplicates(client) == []


def test_a_scan_of_a_product_already_made_puts_nothing_more_in_review(
    client: TestClient, token: str, editor: TestClient
) -> None:
    _from_the_catalog(editor, "var-black")
    scan(client, token, NEAR_BLACK, "received")

    scan(client, token, SyntheticTag(color_rgba="050505FF"), "received")

    assert len(_duplicates(client)) == 1


def test_every_candidate_within_the_cutoff_is_listed(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")
    jade = _from_the_catalog(editor, "var-jade")
    assert client.put(
        "/api/v1/settings/catalog", json={"values": {"similarity_cutoff": "45"}}, headers=admin()
    ).is_success

    scan(client, token, SyntheticTag(color_rgba="808080FF"), "received")

    [duplicate] = _duplicates(client)
    assert [c["id"] for c in duplicate["candidates"]] == [black, jade]


def test_same_product_merges_the_candidate_into_the_scanned_product(
    app: FastAPI, client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black", spools=2)
    assert editor.patch(
        f"{PRODUCTS}/{black}", json={"low_stock_threshold": 3}, headers=CSRF
    ).is_success
    assert editor.post(
        f"/api/v1/shopping-list/items/{black}/ordered", json={"spools": 2}, headers=CSRF
    ).is_success
    viewer = signed_in(app, Role.VIEWER)
    assert viewer.post(
        "/api/v1/shopping-list/suggestions", json={"product_id": black, "spools": 1}, headers=CSRF
    ).is_success
    received = scan(client, token, NEAR_BLACK, "received")
    scanned = received["product"]["id"]
    [duplicate] = _duplicates(client)

    response = _same(editor, duplicate, black)

    assert response.status_code == 204, response.text
    [product] = client.get(PRODUCTS, headers=admin()).json()
    assert product["id"] == scanned
    assert (product["material_id"], product["variant_id"]) == ("GFA00", "A00-K00")
    assert (product["color_rgba"], product["display_name"]) == ("050505FF", "PLA Basic #050505")
    assert product["low_stock_threshold"] == 3
    link = product["catalog_link"]
    assert (link["uuid"], link["how"], link["linked_by"]) == ("var-black", "hand", "frank")
    [spool] = client.get("/api/v1/spools", headers=admin()).json()["items"]
    assert spool["product"]["id"] == scanned
    item = _item(client, scanned)
    # Two were on order, and the scanned spool has now arrived.
    assert item["on_order"] == 1
    assert [(r["kind"], r["spools"]) for r in item["reasons"]] == [("low_stock", 3), ("hand", 2)]
    newest = item["shopping_history"][0]
    assert (newest["action"], newest["by"], newest["on_order"]) == ("same_product", "frank", 1)
    assert {"added_by_hand", "ordered", "suggested"} <= {
        e["action"] for e in item["shopping_history"]
    }
    suggestions = client.get("/api/v1/shopping-list", headers=admin()).json()["suggestions"]
    assert [s["product"]["id"] for s in suggestions] == [scanned]
    assert _duplicates(client) == []
    # Undoing the scanned Received gives its one back.
    assert client.post(f"/api/v1/events/{received['event_id']}/revert", headers=admin()).is_success
    assert _item(client, scanned)["on_order"] == 2


def _history_rows(db: Session) -> dict[int, tuple[Any, ...]]:
    db.expire_all()
    return {
        r.id: (r.product_id, r.action, r.spools, r.size_g, r.on_order, r.user_id, r.at)
        for r in db.scalars(select(ShoppingHistory))
    }


def _entries(item: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (e["action"], e["spools"], e["size_g"], e["on_order"], e["by"], e["at"])
        for e in item["shopping_history"]
    ]


def test_same_product_copies_the_candidates_history_and_edits_no_entry(
    client: TestClient, token: str, editor: TestClient, db: Session
) -> None:
    black = _from_the_catalog(editor, "var-black", spools=2)
    assert editor.post(
        f"/api/v1/shopping-list/items/{black}/ordered", json={"spools": 2}, headers=CSRF
    ).is_success
    copied = _entries(_item(client, black))
    scanned = scan(client, token, NEAR_BLACK, "received")["product"]["id"]
    [duplicate] = _duplicates(client)
    before = _history_rows(db)

    assert _same(editor, duplicate, black).status_code == 204

    after = _history_rows(db)
    # No surviving entry changed; the candidate's own went with it.
    assert {i: row for i, row in after.items() if i in before} == {
        i: row for i, row in before.items() if i in after
    }
    assert all(row[0] != black for row in after.values())
    entries = _entries(_item(client, scanned))
    assert entries[0][0] == "same_product"
    assert [e for e in entries if e[0] in {"added_by_hand", "ordered"}] == copied


def test_same_product_carries_over_the_candidates_chosen_size(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")
    assert editor.put(
        f"/api/v1/shopping-list/items/{black}/size", json={"size_g": 500}, headers=CSRF
    ).is_success
    scanned = scan(client, token, NEAR_BLACK, "received")["product"]["id"]
    [duplicate] = _duplicates(client)

    assert _same(editor, duplicate, black).status_code == 204

    assert _item(client, scanned)["size"] == {"grams": 500, "source": "chosen"}


def test_same_product_moves_a_dismissal(client: TestClient, token: str, editor: TestClient) -> None:
    black = _from_the_catalog(editor, "var-black")
    # Low on stock with none sealed: it needs 2 and 1 by hand, and stays dismissed at that.
    assert editor.patch(
        f"{PRODUCTS}/{black}", json={"low_stock_threshold": 1}, headers=CSRF
    ).is_success
    assert editor.post(f"/api/v1/shopping-list/items/{black}/dismiss", headers=CSRF).is_success
    scanned = scan(client, token, NEAR_BLACK, "received")["product"]["id"]
    [duplicate] = _duplicates(client)

    assert _same(editor, duplicate, black).status_code == 204

    hidden = _item(client, scanned)
    assert hidden["dismissed_need"] == 3
    body = client.get("/api/v1/shopping-list", headers=admin()).json()
    assert [i["product"]["id"] for i in body["dismissed"]] == [scanned]


def test_same_product_takes_the_candidate_out_of_other_possible_duplicates(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")
    scan(client, token, NEAR_BLACK, "received")
    scan(client, token, SyntheticTag(color_rgba="0A0A0AFF"), "received")
    newer, older = _duplicates(client)

    assert _same(editor, older, black).status_code == 204

    assert _duplicates(client) == []
    assert _post(editor, newer, "keep-separate").status_code == 404


def test_keep_separate_leaves_both_and_bring_back_reopens_it(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")
    scanned = scan(client, token, NEAR_BLACK, "received")["product"]["id"]
    [duplicate] = _duplicates(client)

    assert _post(editor, duplicate, "keep-separate").status_code == 204

    assert _duplicates(client) == []
    assert {p["id"] for p in client.get(PRODUCTS, headers=admin()).json()} == {black, scanned}
    # Keeping it separate twice changes nothing.
    assert _post(editor, duplicate, "keep-separate").status_code == 204

    assert _post(editor, duplicate, "restore").status_code == 204

    assert [d["id"] for d in _duplicates(client)] == [duplicate["id"]]


def test_decided_or_wrong_choices_are_refused(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")
    scanned = scan(client, token, NEAR_BLACK, "received")["product"]["id"]
    [duplicate] = _duplicates(client)

    assert _same(editor, duplicate, scanned).status_code == 409
    assert _post(editor, duplicate, "restore").status_code == 409
    assert _same(editor, duplicate, black).status_code == 204
    assert _same(editor, duplicate, black).status_code == 409
    assert _post(editor, duplicate, "keep-separate").status_code == 409
    assert _post(editor, duplicate, "restore").status_code == 409
    assert _post(editor, {"id": 99}, "keep-separate").status_code == 404


def test_a_candidate_with_spools_cannot_be_merged(
    client: TestClient, token: str, editor: TestClient
) -> None:
    black = _from_the_catalog(editor, "var-black")
    scan(client, token, NEAR_BLACK, "received")
    [duplicate] = _duplicates(client)
    assert editor.post(
        "/api/v1/spools",
        json={"product_id": black},
        headers=CSRF,
    ).is_success

    response = _same(editor, duplicate, black)

    assert response.status_code == 409
    assert "spools" in response.json()["detail"]
