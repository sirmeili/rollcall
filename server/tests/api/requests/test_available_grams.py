"""Available grams across the app (#163): per product on the stock summary (which the request
form's picker reads), and held and available grams on a spool, with the requests holding it
for Editors and Admins and the over-held flag."""

from typing import Any

import pytest
from api_helpers import CSRF, admin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import approve, person, put_in, stock, submitted
from sqlalchemy import update
from sqlalchemy.orm import Session

from filament_tracker.db.models import Spool
from filament_tracker.domain.enums import Role, SpoolState

INVENTORY = "/api/v1/inventory"


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _product_choice(product_id: int) -> list[dict[str, Any]]:
    return [{"product_id": product_id, "note": ""}]


def _summary(client: TestClient, product_id: int) -> dict[str, Any]:
    return next(
        p for p in client.get(INVENTORY, headers=admin()).json() if p["product"]["id"] == product_id
    )


def test_the_stock_summary_has_each_products_grams_not_held(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    stock(client, token, "000000FF", "PLA", "received")
    approve(frank, submitted(sam, choices=_product_choice(pla)), grams=300)

    summary = _summary(client, pla)

    assert (summary["available_g"], summary["available_unknown"]) == (1700, False)
    product = client.get(f"/api/v1/products/{pla}", headers=admin()).json()
    assert (product["available_g"], product["available_unknown"]) == (1700, False)


def test_an_open_spool_with_unknown_grams_makes_its_products_grams_unknown(
    client: TestClient, token: str, db: Session
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received", "opened")
    stock(client, token, "000000FF", "PLA", "received")
    db.execute(update(Spool).where(Spool.state == SpoolState.OPEN).values(grams_left_g=None))
    db.commit()

    summary = _summary(client, pla)

    assert (summary["available_g"], summary["available_unknown"]) == (1000, True)


def _spool_of(client: TestClient, product_id: int) -> int:
    spools = client.get(f"/api/v1/spools?product_id={product_id}", headers=admin()).json()
    [spool] = spools["items"]
    return spool["id"]


def test_a_spool_shows_its_held_and_available_grams_and_the_requests_holding_it(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    lamp = submitted(sam, choices=_product_choice(pla))
    vase = submitted(sam, title="Vase", choices=_product_choice(pla))
    approve(frank, lamp, grams=300)
    approve(frank, vase, grams=200)

    spool = frank.get(f"/api/v1/spools/{_spool_of(client, pla)}").json()

    assert (spool["grams_left_g"], spool["held_g"], spool["available_g"]) == (1000, 500, 500)
    assert spool["over_held"] is False
    assert spool["holding_requests"] == [
        {"id": lamp["id"], "title": "Lithophane lamp shade"},
        {"id": vase["id"], "title": "Vase"},
    ]


def test_a_spool_held_beyond_its_grams_left_shows_none_available_and_over_held(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    spool_id = _spool_of(client, pla)
    approve(frank, submitted(sam, choices=_product_choice(pla)), grams=600)
    frank.patch(f"/api/v1/spools/{spool_id}", json={"grams_left_g": 400}, headers=CSRF)

    spool = frank.get(f"/api/v1/spools/{spool_id}").json()

    assert (spool["held_g"], spool["available_g"], spool["over_held"]) == (600, 0, True)


def test_the_holds_of_a_printing_request_do_not_make_a_spool_over_held(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    spool_id = _spool_of(client, pla)
    printing = submitted(sam, choices=_product_choice(pla))
    approve(frank, printing, grams=600)
    put_in(frank, printing["id"], "printing")
    frank.patch(f"/api/v1/spools/{spool_id}", json={"grams_left_g": 400}, headers=CSRF)

    spool = frank.get(f"/api/v1/spools/{spool_id}").json()

    assert (spool["held_g"], spool["available_g"], spool["over_held"]) == (600, 0, False)


def test_an_edit_answers_with_the_held_grams_too(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    spool_id = _spool_of(client, pla)
    lamp = submitted(sam, choices=_product_choice(pla))
    approve(frank, lamp, grams=600)

    response = frank.patch(f"/api/v1/spools/{spool_id}", json={"grams_left_g": 400}, headers=CSRF)

    spool = response.json()
    assert (spool["held_g"], spool["available_g"], spool["over_held"]) == (600, 0, True)
    assert spool["holding_requests"] == [{"id": lamp["id"], "title": "Lithophane lamp shade"}]
