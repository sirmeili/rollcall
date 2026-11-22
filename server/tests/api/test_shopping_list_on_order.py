"""On order over the API: Ordered and setting on order, to buy from need and on order, the
history they write, and spools arriving from a scan or by hand taking one off."""

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_shopping_list import LIST
from test_shopping_list_by_hand import _black, _items

from filament_tracker.db.models import Product
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

HAND = f"{LIST}/hand-reasons"


def ordered_path(product_id: int) -> str:
    return f"{LIST}/items/{product_id}/ordered"


def on_order_path(product_id: int) -> str:
    return f"{LIST}/items/{product_id}/on-order"


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR, username="frank")


def _only(body: dict) -> dict:
    [item] = _items(body)
    return item


def test_ordered_adds_to_on_order_and_takes_it_off_to_buy(editor: TestClient, db: Session) -> None:
    black = _black(db)
    editor.post(HAND, json={"product_id": black.id, "spools": 3}, headers=CSRF)

    response = editor.post(ordered_path(black.id), json={"spools": 2}, headers=CSRF)

    assert response.status_code == 200
    item = _only(response.json())
    assert (item["need"], item["on_order"], item["to_buy"]) == (3, 2, 1)
    entry = item["shopping_history"][0]
    assert (entry["action"], entry["spools"], entry["on_order"], entry["by"]) == (
        "ordered",
        2,
        2,
        "frank",
    )


def test_setting_on_order_replaces_it_and_reads_as_a_change(
    editor: TestClient, db: Session
) -> None:
    black = _black(db)
    editor.post(ordered_path(black.id), json={"spools": 2}, headers=CSRF)

    response = editor.put(on_order_path(black.id), json={"on_order": 5}, headers=CSRF)

    assert response.status_code == 200
    item = _only(response.json())
    assert (item["need"], item["on_order"], item["to_buy"]) == (0, 5, 0)
    assert [(e["action"], e["spools"], e["on_order"]) for e in item["shopping_history"]] == [
        ("on_order_changed", None, 5),
        ("ordered", 2, 2),
    ]


def test_an_item_with_no_need_and_nothing_on_order_leaves_the_list(
    editor: TestClient, db: Session
) -> None:
    black = _black(db)
    editor.post(ordered_path(black.id), json={"spools": 1}, headers=CSRF)

    body = editor.put(on_order_path(black.id), json={"on_order": 0}, headers=CSRF).json()

    assert _items(body) == []


@pytest.mark.parametrize(
    ("path", "method", "body"),
    [
        (ordered_path, "post", {"spools": 0}),
        (on_order_path, "put", {"on_order": -1}),
        (on_order_path, "put", {"on_order": 1000}),
    ],
)
def test_on_order_never_goes_below_0(
    editor: TestClient, db: Session, path, method: str, body: dict
) -> None:  # noqa: ANN001
    black = _black(db)

    response = getattr(editor, method)(path(black.id), json=body, headers=CSRF)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "method", "body"),
    [(ordered_path, "post", {"spools": 1}), (on_order_path, "put", {"on_order": 1})],
)
def test_an_unknown_product_is_not_found(editor: TestClient, path, method: str, body: dict) -> None:  # noqa: ANN001
    response = getattr(editor, method)(path(999), json=body, headers=CSRF)

    assert response.status_code == 404


def test_a_scanned_spool_takes_one_off_and_undoing_it_gives_it_back(
    editor: TestClient, client: TestClient, token: str, db: Session
) -> None:
    scan(client, token, SyntheticTag(), "received")
    [black] = db.query(Product).all()
    editor.post(ordered_path(black.id), json={"spools": 2}, headers=CSRF)

    arrived = scan(client, token, SyntheticTag(), "received")
    assert _only(editor.get(LIST).json())["on_order"] == 1

    client.post(f"/api/v1/events/{arrived['event_id']}/revert", headers=admin())
    assert _only(editor.get(LIST).json())["on_order"] == 2


def test_a_placeholder_added_by_hand_takes_one_off(editor: TestClient, db: Session) -> None:
    black = _black(db)
    editor.post(ordered_path(black.id), json={"spools": 2}, headers=CSRF)

    response = editor.post(
        "/api/v1/spools",
        json={"product_id": black.id},
        headers=CSRF,
    )

    assert response.status_code == 201, response.text
    assert _only(editor.get(LIST).json())["on_order"] == 1
