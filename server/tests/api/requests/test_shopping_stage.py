"""A short choice on a request's detail shows its product's shopping list item stage: on the
list, partly ordered or ordered, to anyone who may see the request, and nothing once the
item is gone."""

from typing import Any

import pytest
from api_helpers import CSRF
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, approve, move, person, stock, submitted
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.models import User
from filament_tracker.domain.enums import Role
from filament_tracker.print_requests.interface import PrintRequests

LIST = "/api/v1/shopping-list"
BLACK_PLA = "000000FF"


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _approved(sam: TestClient, frank: TestClient, grams: int, **body: Any) -> dict[str, Any]:
    created = submitted(sam, **body)
    response = approve(frank, created, grams)
    assert response.status_code == 200, response.text
    return response.json()


def _shopping(user: TestClient, request: dict[str, Any]) -> list[dict[str, Any] | None]:
    """Each choice's shopping list stage, as the user sees the request."""
    response = user.get(f"{REQUESTS}/{request['id']}")
    assert response.status_code == 200, response.text
    return [choice["shopping"] for choice in response.json()["choices"]]


def _product(frank: TestClient) -> int:
    [line] = frank.get(LIST).json()["lines"]
    [item] = line["items"]
    return item["product"]["id"]


def test_a_short_choice_shows_its_item_on_the_shopping_list(
    sam: TestClient, frank: TestClient
) -> None:
    approved = _approved(sam, frank, 300)

    product = _product(frank)
    assert _shopping(frank, approved) == [
        {"stage": "on_list", "product_id": product, "on_order": 0, "need": 1}
    ]


def _ordered(frank: TestClient, product: int, spools: int) -> None:
    response = frank.post(f"{LIST}/items/{product}/ordered", json={"spools": spools}, headers=CSRF)
    assert response.status_code == 200, response.text


def test_a_choice_partly_ordered_shows_how_many_of_its_need_are_ordered(
    sam: TestClient, frank: TestClient
) -> None:
    approved = _approved(sam, frank, 2500)
    product = _product(frank)

    _ordered(frank, product, 1)

    assert _shopping(frank, approved) == [
        {"stage": "partly_ordered", "product_id": product, "on_order": 1, "need": 3}
    ]


def test_a_choice_with_nothing_left_to_buy_shows_ordered(
    sam: TestClient, frank: TestClient
) -> None:
    approved = _approved(sam, frank, 300)
    product = _product(frank)

    _ordered(frank, product, 1)

    assert _shopping(frank, approved) == [
        {"stage": "ordered", "product_id": product, "on_order": 1, "need": 1}
    ]


def test_a_requester_sees_the_stage_on_their_own_request(
    sam: TestClient, frank: TestClient
) -> None:
    approved = _approved(sam, frank, 2500)
    product = _product(frank)
    _ordered(frank, product, 2)

    assert _shopping(sam, approved) == [
        {"stage": "partly_ordered", "product_id": product, "on_order": 2, "need": 3}
    ]


def test_two_requests_short_of_one_product_show_its_one_stage(
    sam: TestClient, frank: TestClient
) -> None:
    first = _approved(sam, frank, 300)
    second = _approved(sam, frank, 800, title="Desk tidy")
    product = _product(frank)
    _ordered(frank, product, 1)

    stage = {"stage": "partly_ordered", "product_id": product, "on_order": 1, "need": 2}
    assert _shopping(frank, first) == [stage]
    assert _shopping(sam, second) == [stage]


def test_a_choice_not_short_shows_nothing(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    approved = _approved(sam, frank, 500, choices=[{"product_id": pla, "note": ""}])

    assert _shopping(frank, approved) == [None]


def test_a_request_that_stops_holding_shows_nothing(sam: TestClient, frank: TestClient) -> None:
    approved = _approved(sam, frank, 300)

    for from_status, to_status in [("waiting_on_filament", "queued"), ("queued", "printing")]:
        response = move(frank, approved["id"], from_status, to_status)
        assert response.status_code == 200, response.text

    assert _shopping(frank, approved) == [None]


def test_a_dismissed_item_shows_nothing_until_it_shows_again(
    sam: TestClient, frank: TestClient
) -> None:
    first = _approved(sam, frank, 300)
    product = _product(frank)
    response = frank.post(f"{LIST}/items/{product}/dismiss", headers=CSRF)
    assert response.status_code == 200, response.text

    assert _shopping(frank, first) == [None]

    second = _approved(sam, frank, 800, title="Desk tidy")

    stage = {"stage": "on_list", "product_id": product, "on_order": 0, "need": 2}
    assert _shopping(frank, first) == [stage]
    assert _shopping(frank, second) == [stage]


def test_reading_a_request_commits_nothing(
    app: FastAPI, db: Session, sam: TestClient, frank: TestClient
) -> None:
    """Reading the stage leaves clearing dismissals to the shopping list's own reads
    (ADR-0021, ADR-0023)."""
    approved = _approved(sam, frank, 300)
    product = _product(frank)
    commits: list[Session] = []
    event.listen(db, "after_commit", commits.append)
    admin = db.scalars(select(User).where(User.username == "frank")).one()

    detail = PrintRequests(db, app.state.print_requests).detail(
        Principal(user=admin), approved["id"]
    )

    [choice] = detail.choices
    assert choice.shopping is not None and choice.shopping.product_id == product
    assert commits == []
