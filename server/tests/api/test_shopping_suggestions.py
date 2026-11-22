"""Suggestions over the API: a Viewer suggests a product or a catalog color, it waits in the
list's suggestions counting toward nothing, and an Editor adds or dismisses it."""

import pytest
from api_helpers import CSRF, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_shopping_list import JADE, LIST, _jade_white_in_the_catalog
from test_shopping_list_by_hand import _black, _items

from filament_tracker.db.catalog_models import CatalogSize, CatalogVariant
from filament_tracker.db.models import Product
from filament_tracker.domain.enums import Role

SUGGESTIONS = f"{LIST}/suggestions"


@pytest.fixture
def viewer(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.VIEWER, username="vic")


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR, username="frank")


def test_a_viewers_suggested_product_waits_in_the_suggestions_counting_toward_nothing(
    viewer: TestClient, db: Session
) -> None:
    black = _black(db)

    response = viewer.post(SUGGESTIONS, json={"product_id": black.id, "spools": 2}, headers=CSRF)

    assert response.status_code == 200
    body = response.json()
    assert _items(body) == []
    [waiting] = body["suggestions"]
    assert waiting["product"]["id"] == black.id
    assert waiting["catalog_color"] is None
    assert (waiting["spools"], waiting["by"]) == (2, "vic")
    assert viewer.get(LIST).json()["suggestions"] == [waiting]


def test_a_suggested_catalog_color_shows_the_color_and_makes_no_product(
    viewer: TestClient, db: Session
) -> None:
    _jade_white_in_the_catalog(db)

    body = viewer.post(SUGGESTIONS, json={"catalog_color": JADE, "spools": 1}, headers=CSRF).json()

    [waiting] = body["suggestions"]
    assert waiting["product"] is None
    assert waiting["catalog_color"] == {
        "uuid": JADE,
        "name": "Jade White",
        "line": "PLA Basic",
        "hexes": ["F5F5F0"],
        "bambu_code": "10100",
    }
    assert db.query(Product).count() == 0


def test_adding_a_suggested_catalog_color_makes_its_from_the_catalog_product(
    viewer: TestClient, editor: TestClient, db: Session
) -> None:
    _jade_white_in_the_catalog(db)
    body = viewer.post(SUGGESTIONS, json={"catalog_color": JADE, "spools": 3}, headers=CSRF).json()
    suggestion = body["suggestions"][0]["id"]

    response = editor.post(f"{SUGGESTIONS}/{suggestion}/add", headers=CSRF)

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == []
    [item] = _items(body)
    assert item["product"]["from_catalog"] is True
    assert item["to_buy"] == 3
    [reason] = item["reasons"]
    assert (reason["kind"], reason["spools"], reason["by"]) == ("hand", 3, "frank")
    assert [(e["action"], e["by"]) for e in item["history"]] == [
        ("suggestion_added", "frank"),
        ("suggested", "vic"),
    ]


def test_a_dismissed_suggestion_leaves_the_suggestions(
    viewer: TestClient, editor: TestClient, db: Session
) -> None:
    black = _black(db)
    body = viewer.post(SUGGESTIONS, json={"product_id": black.id, "spools": 2}, headers=CSRF).json()
    suggestion = body["suggestions"][0]["id"]

    response = editor.post(f"{SUGGESTIONS}/{suggestion}/dismiss", headers=CSRF)

    assert response.status_code == 200
    assert response.json()["suggestions"] == []
    assert _items(response.json()) == []
    assert editor.post(f"{SUGGESTIONS}/{suggestion}/add", headers=CSRF).status_code == 409
    assert editor.post(f"{SUGGESTIONS}/{suggestion}/dismiss", headers=CSRF).status_code == 409


@pytest.mark.parametrize("decision", ["add", "dismiss"])
def test_deciding_a_suggestion_that_is_not_there_is_not_found(
    editor: TestClient, decision: str
) -> None:
    assert editor.post(f"{SUGGESTIONS}/99/{decision}", headers=CSRF).status_code == 404


def test_adding_a_suggested_color_the_catalog_has_dropped_is_refused(
    viewer: TestClient, editor: TestClient, db: Session
) -> None:
    _jade_white_in_the_catalog(db)
    body = viewer.post(SUGGESTIONS, json={"catalog_color": JADE, "spools": 1}, headers=CSRF).json()
    suggestion = body["suggestions"][0]["id"]
    # A catalog sync drops the color.
    db.query(CatalogSize).delete()
    db.query(CatalogVariant).delete()
    db.commit()

    listed = editor.get(LIST).json()["suggestions"]
    assert listed[0]["catalog_color"] == {
        "uuid": JADE,
        "name": None,
        "line": None,
        "hexes": None,
        "bambu_code": None,
    }
    assert editor.post(f"{SUGGESTIONS}/{suggestion}/add", headers=CSRF).status_code == 409
    assert editor.post(f"{SUGGESTIONS}/{suggestion}/dismiss", headers=CSRF).status_code == 200


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
def test_a_bad_suggestion_is_refused(
    viewer: TestClient, db: Session, body: dict, status: int
) -> None:
    _black(db)

    assert viewer.post(SUGGESTIONS, json=body, headers=CSRF).status_code == status
    assert viewer.get(LIST).json()["suggestions"] == []
