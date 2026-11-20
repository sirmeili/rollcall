"""Approving with grams: the grams each filament choice needs, the holds Approve places, and
the automatic move on to Queued or Waiting on Filament, with one email to the requester."""

from typing import Any

import pytest
from api_helpers import CSRF, admin, scan
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox, text_of
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from ofdb_fake import FakeSource, changed_export, gz, ok, refresh, variant
from request_helpers import BLACK, JADE_WHITE, REQUESTS, person, stock, submitted

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

TITLE = "Lithophane lamp shade"


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    """A Requester with an email address."""
    user = person(app, "sam")
    user.patch("/api/v1/auth/me", json={"email": "sam@example.com"}, headers=CSRF)
    return user


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def approve(
    user: TestClient, request: dict[str, Any], grams: dict[str, Any], note: str = ""
) -> Response:
    return user.post(
        f"{REQUESTS}/{request['id']}/moves",
        json={"from_status": "submitted", "to_status": "approved", "note": note, "grams": grams},
        headers=CSRF,
    )


def _read(user: TestClient, request_id: int) -> dict[str, Any]:
    return user.get(f"{REQUESTS}/{request_id}").json()


def _ids(request: dict[str, Any]) -> list[str]:
    return [str(choice["id"]) for choice in request["choices"]]


def _product(product_id: int) -> dict[str, Any]:
    return {"product_id": product_id, "note": ""}


def test_approve_without_grams_for_every_choice_is_refused_per_choice(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla), {"catalog_color": JADE_WHITE, "note": ""}])
    first, second = _ids(created)

    response = approve(frank, created, {first: 50})

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {
        f"grams.{second}": "Give the grams for this filament."
    }
    assert _read(sam, created["id"])["status"] == "submitted"


@pytest.mark.parametrize("grams", [0, -5, 100_001])
def test_grams_out_of_range_are_refused(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, grams: int
) -> None:
    created = submitted(sam)
    [choice] = _ids(created)

    response = approve(frank, created, {choice: grams})

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {
        f"grams.{choice}": "Grams must be 1 to 100,000."
    }


def test_grams_for_a_choice_the_request_does_not_have_are_refused(
    sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    [choice] = _ids(created)

    response = approve(frank, created, {choice: 10, "999999": 10})

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {"grams": "Give grams only for its filaments."}


def test_grams_are_taken_only_by_approve(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    [choice] = _ids(created)

    response = frank.post(
        f"{REQUESTS}/{created['id']}/moves",
        json={
            "from_status": "submitted",
            "to_status": "rejected",
            "note": "No.",
            "grams": {choice: 5},
        },
        headers=CSRF,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {
        "grams": "Grams are given only when approving."
    }


def test_approve_holds_the_grams_and_queues_a_covered_request(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])
    [choice] = _ids(created)

    response = approve(frank, created, {choice: 120}, "  Soon.  ")

    assert response.status_code == 200, response.text
    read = response.json()
    assert read["status"] == "queued"
    [shown] = read["choices"]
    assert (shown["grams"], shown["short_g"]) == (120, 0)
    assert [(h["product_id"], h["grams"]) for h in shown["holds"]] == [(pla, 120)]
    assert shown["available_g"] == 880


def test_history_shows_approved_by_the_admin_then_the_automatic_move(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])

    approve(frank, created, {_ids(created)[0]: 120}, "Soon.")

    newest, approved = _read(sam, created["id"])["history"][:2]
    assert (
        approved["username"],
        approved["from_value"],
        approved["to_value"],
        approved["note"],
        approved["automatic"],
    ) == ("frank", "submitted", "approved", "Soon.", False)
    assert (
        newest["username"],
        newest["from_value"],
        newest["to_value"],
        newest["note"],
        newest["automatic"],
    ) == (None, "approved", "queued", None, True)


def test_a_request_short_of_filament_waits_holding_what_there_is(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])

    read = approve(frank, created, {_ids(created)[0]: 1500}).json()

    assert read["status"] == "waiting_on_filament"
    [shown] = read["choices"]
    assert shown["short_g"] == 500
    assert [h["grams"] for h in shown["holds"]] == [1000]
    assert read["history"][0]["to_value"] == "waiting_on_filament"
    assert read["history"][0]["automatic"] is True


def test_a_catalog_color_with_no_product_in_stock_is_short_its_whole_grams(
    sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam, choices=[{"catalog_color": JADE_WHITE, "note": ""}])

    read = approve(frank, created, {_ids(created)[0]: 300}).json()

    assert read["status"] == "waiting_on_filament"
    [shown] = read["choices"]
    assert (shown["short_g"], shown["holds"], shown["available_g"]) == (300, [], 0)


def test_a_catalog_color_is_held_on_the_product_linked_to_it(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    # This tag's ID links to Black in the catalog.
    linked = scan(client, token, SyntheticTag(variant_id="A00-K0"), "received")["product"]["id"]
    created = submitted(sam, choices=[{"catalog_color": BLACK, "note": ""}])

    read = approve(frank, created, {_ids(created)[0]: 200}).json()

    assert read["status"] == "queued"
    assert [(h["product_id"], h["grams"]) for h in read["choices"][0]["holds"]] == [(linked, 200)]


def test_grams_are_never_promised_twice(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    first = submitted(sam, choices=[_product(pla)])
    second = submitted(sam, choices=[_product(pla)])
    approve(frank, first, {_ids(first)[0]: 700})

    read = approve(frank, second, {_ids(second)[0]: 700}).json()

    assert read["status"] == "waiting_on_filament"
    assert read["choices"][0]["short_g"] == 400
    assert _read(frank, first["id"])["choices"][0]["short_g"] == 0


@pytest.mark.parametrize(("grams", "held"), [(100, True), (5000, False)])
def test_the_requester_sees_only_whether_each_choice_is_held(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, grams: int, held: bool
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])
    approve(frank, created, {_ids(created)[0]: grams})

    [shown] = _read(sam, created["id"])["choices"]

    assert shown["held"] is held
    assert (shown["grams"], shown["short_g"], shown["holds"], shown["available_g"]) == (
        None,
        None,
        None,
        None,
    )
    assert _read(frank, created["id"])["choices"][0]["held"] is held


def test_an_editor_sees_the_holds(
    app: FastAPI, client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])
    approve(frank, created, {_ids(created)[0]: 100})
    editor = person(app, "erin", Role.EDITOR, requester=False)

    [hold] = _read(editor, created["id"])["choices"][0]["holds"]

    assert (hold["product_id"], hold["product_name"], hold["grams"]) == (pla, "PLA #000000", 100)
    assert isinstance(hold["spool_id"], int)


def test_a_submitted_request_has_no_grams_or_shortfall_yet(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])

    [shown] = _read(frank, created["id"])["choices"]

    assert (shown["held"], shown["grams"], shown["short_g"], shown["available_g"]) == (
        None,
        None,
        None,
        1000,
    )


def test_an_admin_token_approves_with_grams(
    client: TestClient, token: str, sam: TestClient
) -> None:
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, choices=[_product(pla)])

    response = client.post(
        f"{REQUESTS}/{created['id']}/moves",
        json={
            "from_status": "submitted",
            "to_status": "approved",
            "grams": {_ids(created)[0]: 50},
        },
        headers=admin(),
    )

    assert response.json()["status"] == "queued"


@pytest.mark.parametrize(
    ("grams", "said"), [(100, "It's queued."), (5000, "It's waiting on filament.")]
)
def test_the_requester_gets_one_email_saying_where_it_went(
    app: FastAPI,
    client: TestClient,
    token: str,
    sam: TestClient,
    frank: TestClient,
    outbox: FakeOutbox,
    grams: int,
    said: str,
) -> None:
    email_on(client)
    pla = stock(client, token, "000000FF", "PLA", "received")
    created = submitted(sam, title=TITLE, choices=[_product(pla)])
    sent(app, outbox)

    approve(frank, created, {_ids(created)[0]: grams})

    [message] = sent(app, outbox)
    assert message["Subject"] == f"Your print request was approved: {TITLE}"
    assert text_of(message).startswith(f'Your print request "{TITLE}" was approved. {said}\n')


def test_a_catalog_color_merged_into_another_is_held_on_the_product_linked_to_that(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, ofdb: FakeSource
) -> None:
    pla = stock(client, token, "FFFFFFFF", "PLA", "received")
    client.patch(
        f"/api/v1/products/{pla}", json={"catalog_color": JADE_WHITE}, headers=admin()
    ).raise_for_status()
    created = submitted(sam, choices=[{"catalog_color": JADE_WHITE, "note": ""}])
    merged = changed_export()
    merged["variants"].append(
        variant("var-white", "White", "#FFFFFF", "id-fil-pla-basic", moved_from=[JADE_WHITE])
    )
    ofdb.serve(ok(gz(merged), etag='"v2"'))
    refresh(client)

    read = approve(frank, created, {_ids(created)[0]: 100}).json()

    assert read["status"] == "queued"
    assert [h["product_id"] for h in read["choices"][0]["holds"]] == [pla]
