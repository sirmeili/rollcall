"""The shopping list over the API with the real Print Requests wired in: approved requests
short of filament put it on the list, Approve gives an unowned catalog color its "From the
catalog" product, reasons go by themselves, and choosing an item's size."""

from typing import Any

import pytest
from api_helpers import CSRF, admin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, changed_export, gz, ok, refresh
from request_helpers import JADE_WHITE, REQUESTS, approve, person, stock, submitted

from filament_tracker.domain.enums import Role

LIST = "/api/v1/shopping-list"
BLACK_PLA = "000000FF"


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _items(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for line in body["lines"] for i in line["items"]] + body["not_in_catalog"]


def _requests(user: TestClient) -> list[tuple[int | None, str | None, int]]:
    """Every request reason on the list: its request, title and grams short."""
    return [
        (r["request_id"], r["title"], r["short_g"])
        for item in _items(user.get(LIST).json())
        for r in item["reasons"]
        if r["kind"] == "request"
    ]


def _approved(sam: TestClient, frank: TestClient, grams: int, **body: Any) -> dict[str, Any]:
    created = submitted(sam, **body)
    response = approve(frank, created, grams)
    assert response.status_code == 200, response.text
    return response.json()


def _move(user: TestClient, request: dict[str, Any], to_status: str) -> dict[str, Any]:
    status = user.get(f"{REQUESTS}/{request['id']}").json()["status"]
    note = "Not needed." if to_status in ("cancelled", "rejected") else ""
    response = user.post(
        f"{REQUESTS}/{request['id']}/moves",
        json={"from_status": status, "to_status": to_status, "note": note},
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_approving_an_unowned_catalog_color_makes_its_from_the_catalog_product_on_the_list(
    sam: TestClient, frank: TestClient
) -> None:
    approved = _approved(sam, frank, 300)
    assert approved["status"] == "waiting_on_filament"

    [line] = frank.get(LIST).json()["lines"]
    [item] = line["items"]
    product = item["product"]
    assert (product["display_name"], product["provisional"], product["from_catalog"]) == (
        "Jade White PLA Basic",
        True,
        True,
    )
    link = product["catalog_link"]
    assert (link["uuid"], link["how"], link["linked_by"]) == (JADE_WHITE, "hand", "frank")
    assert item["reasons"] == [
        {
            "kind": "request",
            "request_id": approved["id"],
            "title": "Lithophane lamp shade",
            "short_g": 300,
        }
    ]
    assert item["to_buy"] == 1
    assert item["size"] == {"grams": 1000, "source": "default"}


def test_two_requests_short_300_g_each_on_one_product_need_1_spool(
    sam: TestClient, frank: TestClient
) -> None:
    first = _approved(sam, frank, 300)
    second = _approved(sam, frank, 300, title="Desk tidy")

    [line] = frank.get(LIST).json()["lines"]
    [item] = line["items"]
    assert item["to_buy"] == 1
    assert [(r["request_id"], r["short_g"]) for r in item["reasons"]] == [
        (first["id"], 300),
        (second["id"], 300),
    ]


def test_a_submitted_request_adds_nothing(sam: TestClient, frank: TestClient) -> None:
    submitted(sam)

    assert _items(frank.get(LIST).json()) == []


def test_rejecting_a_submitted_request_adds_nothing(sam: TestClient, frank: TestClient) -> None:
    created = submitted(sam)

    _move(frank, created, "rejected")

    assert _requests(frank) == []


@pytest.mark.parametrize(
    "steps", [("cancelled",), ("queued", "printing"), ("queued", "printing", "done")]
)
def test_a_request_that_stops_holding_loses_its_reason(
    sam: TestClient, frank: TestClient, steps: tuple[str, ...]
) -> None:
    approved = _approved(sam, frank, 300)
    assert len(_requests(frank)) == 1

    for to_status in steps:
        _move(frank, approved, to_status)

    assert _requests(frank) == []


def test_a_request_once_fully_held_loses_its_reason(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    approved = _approved(sam, frank, 1500, choices=[{"product_id": pla, "note": ""}])
    assert _requests(frank) == [(approved["id"], "Lithophane lamp shade", 500)]

    # A second spool arrives: the waiting request is retried, takes it and is covered.
    stock(client, token, "000000FF", "PLA", "received")

    assert _requests(frank) == []


def test_a_catalog_color_the_catalog_has_dropped_gets_no_product(
    client: TestClient, ofdb: FakeSource, sam: TestClient, frank: TestClient
) -> None:
    created = submitted(sam)
    ofdb.serve(ok(gz(changed_export()), etag='"v2"'))
    refresh(client)

    assert approve(frank, created, 300).json()["status"] == "waiting_on_filament"

    assert _items(frank.get(LIST).json()) == []


def test_choosing_a_size_re_rounds_the_requests_part_and_goes_into_the_history(
    sam: TestClient, frank: TestClient
) -> None:
    _approved(sam, frank, 2500)
    [line] = frank.get(LIST).json()["lines"]
    [item] = line["items"]
    assert item["to_buy"] == 3

    response = frank.put(
        f"{LIST}/items/{item['product']['id']}/size", json={"size_g": 3000}, headers=CSRF
    )

    assert response.status_code == 200
    [line] = response.json()["lines"]
    [item] = line["items"]
    assert item["size"] == {"grams": 3000, "source": "chosen"}
    assert item["to_buy"] == 1
    [entry] = item["history"]
    assert (entry["action"], entry["size_g"], entry["by"]) == ("size_changed", 3000, "frank")


@pytest.mark.parametrize("size_g", [0, 10_001])
def test_a_size_out_of_range_is_refused(frank: TestClient, size_g: int) -> None:
    response = frank.put(f"{LIST}/items/1/size", json={"size_g": size_g}, headers=CSRF)

    assert response.status_code == 422


def test_choosing_the_size_of_no_product_is_not_found(frank: TestClient) -> None:
    response = frank.put(f"{LIST}/items/999/size", json={"size_g": 1000}, headers=CSRF)

    assert response.status_code == 404


# --- Who sees each request named --------------------------------------------------------------


@pytest.fixture
def two_requests(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> tuple[dict[str, Any], dict[str, Any]]:
    """An approved request of sam's, and one of vic's."""
    vic = person(app, "vic")
    return _approved(sam, frank, 300), _approved(vic, frank, 300, title="Vic's vase")


def test_a_requester_sees_their_own_requests_named_and_others_as_a_print_request(
    sam: TestClient, two_requests: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    mine, _ = two_requests

    assert _requests(sam) == [(mine["id"], "Lithophane lamp shade", 300), (None, None, 300)]


@pytest.mark.parametrize("role", [Role.EDITOR, Role.ADMIN])
def test_editors_and_admins_see_every_request_named(
    app: FastAPI, role: Role, two_requests: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    mine, vics = two_requests
    staff = person(app, "pat", role, requester=False)

    assert _requests(staff) == [
        (mine["id"], "Lithophane lamp shade", 300),
        (vics["id"], "Vic's vase", 300),
    ]


def test_a_viewer_with_no_requests_sees_none_named(
    app: FastAPI, two_requests: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    viewer = person(app, "val", requester=False)

    assert _requests(viewer) == [(None, None, 300), (None, None, 300)]


@pytest.mark.parametrize(
    ("role", "named"), [(Role.VIEWER, False), (Role.EDITOR, True), (Role.ADMIN, True)]
)
def test_a_machine_token_sees_requests_named_by_its_role(
    client: TestClient,
    role: Role,
    named: bool,
    two_requests: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    made = client.post("/api/v1/tokens", json={"name": "Script", "role": role}, headers=admin())
    bearer = {"Authorization": f"Bearer {made.json()['token']}"}

    body = client.get(LIST, headers=bearer).json()

    titles = [r["title"] for item in _items(body) for r in item["reasons"]]
    assert titles == (["Lithophane lamp shade", "Vic's vase"] if named else [None, None])


def test_an_item_on_the_list_only_for_a_request_stays_dismissed_until_more_is_needed(
    sam: TestClient, frank: TestClient
) -> None:
    _approved(sam, frank, 300)
    [line] = frank.get(LIST).json()["lines"]
    [item] = line["items"]
    dismissed = frank.post(f"{LIST}/items/{item['product']['id']}/dismiss", headers=CSRF)
    assert dismissed.status_code == 200, dismissed.text

    body = frank.get(LIST).json()
    assert body["lines"] == []
    [hidden] = body["dismissed"]
    assert (hidden["need"], hidden["dismissed_need"]) == (1, 1)

    _approved(sam, frank, 800, title="Desk tidy")

    [line] = frank.get(LIST).json()["lines"]
    [shown] = line["items"]
    assert shown["need"] == 2
