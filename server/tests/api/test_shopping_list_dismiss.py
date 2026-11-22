"""Dismiss and Bring back over the API: a dismissed item leaves the list for its Dismissed
items, with what's new once more of it is needed, and is in the item's history."""

import pytest
from api_helpers import CSRF, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_shopping_list import LIST

from filament_tracker.db.models import Product, Spool
from filament_tracker.domain.enums import Role, SpoolState


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR, username="frank")


def _low(db: Session, threshold: int = 1) -> Product:
    """A product with no spools: it needs threshold + 1."""
    black = Product(
        filament_type="PLA",
        color_rgba="000000FF",
        display_name="Black",
        provisional=True,
        low_stock_threshold=threshold,
    )
    db.add(black)
    db.commit()
    return black


def _items(body: dict) -> list[dict]:
    return [i for line in body["lines"] for i in line["items"]] + body["not_in_catalog"]


def _dismiss(client: TestClient, product: Product):  # noqa: ANN202
    return client.post(f"{LIST}/items/{product.id}/dismiss", headers=CSRF)


def _bring_back(client: TestClient, product: Product):  # noqa: ANN202
    return client.post(f"{LIST}/items/{product.id}/bring-back", headers=CSRF)


def test_a_dismissed_item_moves_to_dismissed(editor: TestClient, db: Session) -> None:
    black = _low(db)

    response = _dismiss(editor, black)

    assert response.status_code == 200
    body = response.json()
    assert _items(body) == []
    [item] = body["dismissed"]
    assert (item["product"]["id"], item["dismissed_need"], item["new_since_dismissal"]) == (
        black.id,
        2,
        None,
    )
    [entry] = item["history"]
    assert (entry["action"], entry["spools"], entry["by"]) == ("dismissed", 2, "frank")
    assert editor.get(LIST).json()["dismissed"] == [item]


def test_dismiss_removes_hand_added_reasons(editor: TestClient, db: Session) -> None:
    black = _low(db)
    editor.post(f"{LIST}/hand-reasons", json={"product_id": black.id, "spools": 3}, headers=CSRF)

    [item] = _dismiss(editor, black).json()["dismissed"]

    assert [r["kind"] for r in item["reasons"]] == ["low_stock"]
    assert item["dismissed_need"] == 5


def test_a_dismissed_item_comes_back_with_whats_new(editor: TestClient, db: Session) -> None:
    black = _low(db)
    _dismiss(editor, black)
    black.low_stock_threshold = 3
    db.commit()

    body = editor.get(LIST).json()

    [item] = _items(body)
    assert (item["to_buy"], item["new_since_dismissal"]) == (4, 2)
    assert body["dismissed"] == []


def test_a_dismissal_is_cleared_once_the_need_reaches_0(editor: TestClient, db: Session) -> None:
    black = _low(db)
    _dismiss(editor, black)
    db.add_all(Spool(product=black, state=SpoolState.SEALED) for _ in range(2))
    db.commit()
    assert editor.get(LIST).json()["dismissed"] == []

    for spool in black.spools:
        db.delete(spool)
    db.commit()

    body = editor.get(LIST).json()
    [item] = _items(body)
    assert item["dismissed_need"] is None


def test_an_action_route_clears_a_dismissal_once_the_need_reaches_0(
    editor: TestClient, db: Session
) -> None:
    black = _low(db)
    other = _low(db)
    _dismiss(editor, black)
    db.add_all(Spool(product=black, state=SpoolState.SEALED) for _ in range(2))
    db.commit()

    # Only an action's answer reads the list while black needs nothing.
    assert editor.post(
        f"{LIST}/items/{other.id}/ordered", json={"spools": 1}, headers=CSRF
    ).is_success

    for spool in black.spools:
        db.delete(spool)
    db.commit()
    body = editor.get(LIST).json()
    [item] = [i for i in _items(body) if i["product"]["id"] == black.id]
    assert item["dismissed_need"] is None


def test_bring_back_returns_the_item_to_the_list(editor: TestClient, db: Session) -> None:
    black = _low(db)
    _dismiss(editor, black)

    response = _bring_back(editor, black)

    assert response.status_code == 200
    body = response.json()
    assert body["dismissed"] == []
    [item] = _items(body)
    assert item["dismissed_need"] is None
    assert [e["action"] for e in item["history"]] == ["brought_back", "dismissed"]


def test_dismissing_a_product_not_on_the_list_is_refused(editor: TestClient, db: Session) -> None:
    black = _low(db, threshold=0)

    assert _dismiss(editor, black).status_code == 404


def test_dismissing_an_item_already_dismissed_is_refused(editor: TestClient, db: Session) -> None:
    black = _low(db)
    _dismiss(editor, black)

    assert _dismiss(editor, black).status_code == 409


def test_bring_back_on_an_item_not_dismissed_is_refused(editor: TestClient, db: Session) -> None:
    black = _low(db)

    assert _bring_back(editor, black).status_code == 409


def test_dismiss_and_bring_back_on_no_such_product_are_not_found(editor: TestClient) -> None:
    assert editor.post(f"{LIST}/items/99/dismiss", headers=CSRF).status_code == 404
    assert editor.post(f"{LIST}/items/99/bring-back", headers=CSRF).status_code == 404


def test_dismissing_an_item_only_on_order_is_refused(editor: TestClient, db: Session) -> None:
    black = _low(db, threshold=0)
    editor.post(f"{LIST}/items/{black.id}/ordered", json={"spools": 1}, headers=CSRF)

    assert _dismiss(editor, black).status_code == 409
