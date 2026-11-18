"""The rules a request's fields and filament choices follow."""

from datetime import date, timedelta
from typing import Any

import pytest
from api_helpers import CSRF, admin, scan
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import (
    BLACK,
    GRADIENT,
    JADE_WHITE,
    REQUESTS,
    person,
    request_body,
    stock,
    submit,
    submitted,
)

from filament_tracker.decoder.synthetic import SyntheticTag


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


def problems(response: Any) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return response.json()["detail"]["problems"]


def test_every_mistake_is_reported_together(sam: TestClient) -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    found = problems(
        submit(
            sam,
            title="   ",
            quantity=0,
            needed_by=yesterday,
            link="ftp://example.com/model.stl",
            choices=[{"product_id": 999}],
        )
    )

    assert set(found) == {"title", "quantity", "needed_by", "link", "choices"}


@pytest.mark.parametrize("quantity", [0, 101, -3])
def test_quantity_is_1_to_100(sam: TestClient, quantity: int) -> None:
    assert "quantity" in problems(submit(sam, quantity=quantity))


@pytest.mark.parametrize("quantity", [1, 100])
def test_quantity_limits_are_allowed(sam: TestClient, quantity: int) -> None:
    assert submit(sam, quantity=quantity).status_code == 201


def test_today_is_a_valid_needed_by_date(sam: TestClient) -> None:
    assert submit(sam, needed_by=date.today().isoformat()).status_code == 201


@pytest.mark.parametrize(
    "link",
    ["javascript:alert(1)", "makerworld.com/models/1", "https://", "file:///etc/passwd"],
)
def test_a_link_must_be_an_absolute_http_or_https_url(sam: TestClient, link: str) -> None:
    assert "link" in problems(submit(sam, link=link))


@pytest.mark.parametrize("link", ["http://example.com/a", "HTTPS://www.printables.com/model/1"])
def test_http_and_https_links_are_accepted(sam: TestClient, link: str) -> None:
    assert submitted(sam, link=link)["link"] == link


@pytest.mark.parametrize(("field", "size"), [("title", 121), ("notes", 2001), ("link", 2001)])
def test_lengths_are_limited(sam: TestClient, field: str, size: int) -> None:
    value = "https://e.com/" + "a" * (size - 14) if field == "link" else "a" * size

    assert submit(sam, **{field: value}).status_code == 422


def test_a_choice_note_is_up_to_80_characters(sam: TestClient) -> None:
    long = [{"catalog_color": JADE_WHITE, "note": "a" * 81}]
    fits = [{"catalog_color": JADE_WHITE, "note": "a" * 80}]

    assert submit(sam, choices=long).status_code == 422
    assert submit(sam, choices=fits).status_code == 201


def test_with_no_file_and_no_link_the_notes_must_say_where_the_model_is(sam: TestClient) -> None:
    assert "notes" in problems(submit(sam, link=None, notes="  "))
    assert submit(sam, link=None, notes="On the USB stick").status_code == 201


def test_a_request_needs_a_filament_choice(sam: TestClient) -> None:
    assert "choices" in problems(submit(sam, choices=[]))


def test_a_choice_is_a_product_or_a_catalog_color_not_both(sam: TestClient) -> None:
    both = [{"product_id": 1, "catalog_color": JADE_WHITE}]

    assert submit(sam, choices=both).status_code == 422
    assert submit(sam, choices=[{"note": "neither"}]).status_code == 422


def test_an_out_of_stock_product_cannot_be_chosen(
    sam: TestClient, client: TestClient, token: str
) -> None:
    used_up = stock(client, token, "FF6A13FF", "PLA", "received", "opened", "empty")

    assert "choices" in problems(submit(sam, choices=[{"product_id": used_up}]))


def test_an_unknown_catalog_color_cannot_be_chosen(sam: TestClient) -> None:
    assert "choices" in problems(submit(sam, choices=[{"catalog_color": "not-a-color"}]))


def test_choices_are_shown_with_stock_and_similar_colors(
    sam: TestClient, client: TestClient, token: str
) -> None:
    black_pla = stock(client, token, "000000FF", "PLA", "received")
    stock(client, token, "000000FF", "PETG", "received", "opened")
    body = request_body(
        choices=[
            {"product_id": black_pla, "note": "body"},
            {"catalog_color": BLACK},
            {"catalog_color": GRADIENT},
        ]
    )

    product, black, gradient = submitted(sam, **body)["choices"]

    assert (product["kind"], product["material"], product["sealed"], product["open"]) == (
        "product",
        "PLA",
        1,
        0,
    )
    assert (product["note"], product["hexes"]) == ("body", ["000000"])
    assert (black["kind"], black["name"], black["line"]) == (
        "catalog_color",
        "Black PLA Basic",
        "PLA Basic",
    )
    assert black["in_catalog"] is True
    assert [(s["material"], s["different_material"]) for s in black["similar"]] == [
        ("PLA", False),
        ("PETG", True),
    ]
    assert gradient["multi_color"] is True
    assert gradient["similar"] == []


def test_the_detail_carries_the_store_for_find_in_store(sam: TestClient) -> None:
    assert submitted(sam)["store_address"] == "https://us.store.bambulab.com"


def test_a_choice_keeps_its_product_after_the_stock_is_used_up(
    sam: TestClient, client: TestClient, token: str
) -> None:
    tag = SyntheticTag(color_rgba="C12E1FFF", material_id="GFRED", variant_id="RED-C1")
    product = scan(client, token, tag, "received")["product"]["id"]
    created = submitted(sam, choices=[{"product_id": product}])
    scan(client, token, tag, "opened")
    scan(client, token, tag, "empty")

    [choice] = sam.get(f"{REQUESTS}/{created['id']}").json()["choices"]

    assert (choice["product_id"], choice["sealed"], choice["open"]) == (product, 0, 0)


def test_the_tokens_cannot_submit(client: TestClient) -> None:
    response = client.post(REQUESTS, json=request_body(), headers={**admin(), **CSRF})

    assert response.status_code == 403
