"""Releasing holds when a request stops needing them (Done, Failed, Cancelled), and Reprint,
which holds again with grams per choice and lands on Queued or Waiting on Filament."""

from typing import Any

import pytest
from api_helpers import CSRF
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from request_helpers import REQUESTS, person, stock, submitted

from filament_tracker.domain.enums import Role

BLACK_PLA = "000000FF"


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _read(user: TestClient, request_id: int) -> dict[str, Any]:
    return user.get(f"{REQUESTS}/{request_id}").json()


def _move(
    user: TestClient,
    request_id: int,
    from_status: str,
    to_status: str,
    note: str = "",
    grams: dict[str, Any] | None = None,
) -> Response:
    body: dict[str, Any] = {"from_status": from_status, "to_status": to_status, "note": note}
    if grams is not None:
        body["grams"] = grams
    return user.post(f"{REQUESTS}/{request_id}/moves", json=body, headers=CSRF)


def _choice(request: dict[str, Any]) -> str:
    [choice] = request["choices"]
    return str(choice["id"])


def _queued(sam: TestClient, frank: TestClient, product_id: int, grams: int) -> dict[str, Any]:
    """A request of sam's for the product, approved with `grams` and covered: Queued."""
    created = submitted(sam, choices=[{"product_id": product_id, "note": ""}])
    response = _move(frank, created["id"], "submitted", "approved", grams={_choice(created): grams})
    assert response.json()["status"] == "queued", response.text
    return created


def _walk(frank: TestClient, request_id: int, *steps: str) -> dict[str, Any]:
    read = _read(frank, request_id)
    for to_status in steps:
        note = "Not needed." if to_status == "cancelled" else ""
        response = _move(frank, request_id, read["status"], to_status, note)
        assert response.status_code == 200, response.text
        read = response.json()
    return read


# --- Releasing --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "steps", [("printing", "done"), ("printing", "failed"), ("cancelled",)], ids=lambda s: s[-1]
)
def test_done_failed_and_cancelled_release_the_holds_and_free_the_grams(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, steps: tuple[str, ...]
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    created = _queued(sam, frank, pla, 300)

    read = _walk(frank, created["id"], *steps)

    [shown] = read["choices"]
    assert (shown["holds"], shown["short_g"], shown["available_g"]) == ([], None, 1000)


# --- Reprint ----------------------------------------------------------------------------------


def _failed(sam: TestClient, frank: TestClient, product_id: int, grams: int) -> dict[str, Any]:
    created = _queued(sam, frank, product_id, grams)
    return _walk(frank, created["id"], "printing", "failed")


def _reprint(
    frank: TestClient, request: dict[str, Any], grams: dict[str, Any], note: str = ""
) -> Response:
    return _move(frank, request["id"], "failed", "queued", note, grams)


def test_reprint_holds_the_grams_given_and_queues_a_covered_request(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    failed = _failed(sam, frank, pla, 300)

    response = _reprint(frank, failed, {_choice(failed): 450}, "Bed adhesion.")

    assert response.status_code == 200, response.text
    read = response.json()
    assert (read["status"], read["attempt"]) == ("queued", 2)
    [shown] = read["choices"]
    assert (shown["grams"], shown["short_g"], shown["available_g"]) == (450, 0, 550)
    assert [(h["product_id"], h["grams"]) for h in shown["holds"]] == [(pla, 450)]
    entry = read["history"][0]
    assert (
        entry["username"],
        entry["from_value"],
        entry["to_value"],
        entry["note"],
        entry["automatic"],
    ) == ("frank", "failed", "queued", "Bed adhesion.", False)


def test_a_reprint_short_of_filament_waits_holding_what_there_is(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    failed = _failed(sam, frank, pla, 300)

    read = _reprint(frank, failed, {_choice(failed): 1200}).json()

    assert (read["status"], read["attempt"]) == ("waiting_on_filament", 2)
    [shown] = read["choices"]
    assert (shown["grams"], shown["short_g"]) == (1200, 200)
    assert [h["grams"] for h in shown["holds"]] == [1000]
    entry = read["history"][0]
    assert (entry["username"], entry["from_value"], entry["to_value"], entry["automatic"]) == (
        "frank",
        "failed",
        "waiting_on_filament",
        False,
    )


def test_attempts_count_reprints_that_wait_for_filament(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    failed = _failed(sam, frank, pla, 300)
    _reprint(frank, failed, {_choice(failed): 1200})
    _walk(frank, failed["id"], "queued", "printing", "failed")

    read = _reprint(frank, failed, {_choice(failed): 100}).json()

    assert (read["status"], read["attempt"]) == ("queued", 3)


def test_reprint_without_grams_for_every_choice_is_refused_per_choice(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    failed = _failed(sam, frank, pla, 300)

    response = _reprint(frank, failed, {})

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {
        f"grams.{_choice(failed)}": "Give the grams for this filament."
    }
    read = _read(frank, failed["id"])
    assert (read["status"], read["choices"][0]["holds"]) == ("failed", [])


@pytest.mark.parametrize("grams", [0, 100_001])
def test_reprint_grams_out_of_range_are_refused(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, grams: int
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    failed = _failed(sam, frank, pla, 300)

    response = _reprint(frank, failed, {_choice(failed): grams})

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {
        f"grams.{_choice(failed)}": "Grams must be 1 to 100,000."
    }
    assert _read(frank, failed["id"])["status"] == "failed"


@pytest.mark.parametrize("grams", [100, 5000], ids=["queued", "waiting"])
def test_neither_reprint_landing_sends_an_email(
    app: FastAPI,
    client: TestClient,
    token: str,
    sam: TestClient,
    frank: TestClient,
    outbox: FakeOutbox,
    grams: int,
) -> None:
    email_on(client)
    sam.patch("/api/v1/auth/me", json={"email": "sam@example.com"}, headers=CSRF)
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    failed = _failed(sam, frank, pla, 300)
    sent(app, outbox)

    assert _reprint(frank, failed, {_choice(failed): grams}).status_code == 200

    assert sent(app, outbox) == []
