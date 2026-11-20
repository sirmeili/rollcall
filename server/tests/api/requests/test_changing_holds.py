"""An Admin changes a request's holds by hand while it is Approved, Waiting on Filament or
Queued: a choice's grams, a hold's spool or grams, a hold on another product, or no hold.
Each change releases what it replaces as `changed`, writes a `holds_changed` entry, sends no
email, and checks the request again."""

from typing import Any

import pytest
from api_helpers import CSRF, admin
from email_helpers import email_on, sent
from fake_outbox import FakeOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from request_helpers import REQUESTS, person, put_in, stock, submitted
from sqlalchemy import select

from filament_tracker.db.models import SpoolHold
from filament_tracker.domain.enums import ReleaseReason, Role
from filament_tracker.print_requests.holding import NOT_NOW
from filament_tracker.print_requests.pipeline import STALE

BLACK_PLA = "000000FF"
CHARCOAL_PLA = "333333FF"


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def _read(user: TestClient, request_id: int) -> dict[str, Any]:
    return user.get(f"{REQUESTS}/{request_id}").json()


def _approved(sam: TestClient, frank: TestClient, product_id: int, grams: int) -> dict[str, Any]:
    """A request of sam's for the product, approved with `grams`; as Approve left it."""
    created = submitted(sam, choices=[{"product_id": product_id, "note": ""}])
    [choice] = created["choices"]
    response = frank.post(
        f"{REQUESTS}/{created['id']}/moves",
        json={
            "from_status": "submitted",
            "to_status": "approved",
            "note": "",
            "grams": {str(choice["id"]): grams},
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _choice(read: dict[str, Any]) -> dict[str, Any]:
    [choice] = read["choices"]
    return choice


def set_grams(user: TestClient, read: dict[str, Any], grams: int) -> Response:
    return user.put(
        f"{REQUESTS}/{read['id']}/choices/{_choice(read)['id']}/grams",
        json={"from_status": read["status"], "grams": grams},
        headers=CSRF,
    )


def _holds(read: dict[str, Any]) -> list[tuple[int, int]]:
    return [(hold["spool_id"], hold["grams"]) for hold in _choice(read)["holds"]]


# --- A choice's grams -------------------------------------------------------------------------


def test_new_grams_hold_again_and_queue_a_waiting_request_they_cover(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _approved(sam, frank, pla, 1500)
    assert waiting["status"] == "waiting_on_filament"
    [(spool_id, _)] = _holds(waiting)

    response = set_grams(frank, waiting, 800)

    assert response.status_code == 200, response.text
    read = response.json()
    assert read["status"] == "queued"
    assert (_choice(read)["grams"], _choice(read)["short_g"]) == (800, 0)
    assert _holds(read) == [(spool_id, 800)]
    assert [
        (entry["kind"], entry["username"], entry["to_value"], entry["automatic"])
        for entry in read["history"][:2]
    ] == [
        ("status_changed", None, "queued", True),
        ("holds_changed", "frank", None, False),
    ]


def _spool(client: TestClient, product_id: int) -> int:
    [spool] = client.get(f"/api/v1/spools?product_id={product_id}", headers=admin()).json()["items"]
    return spool["id"]


def add_hold(user: TestClient, read: dict[str, Any], spool_id: int, grams: int) -> Response:
    return user.post(
        f"{REQUESTS}/{read['id']}/choices/{_choice(read)['id']}/holds",
        json={"from_status": read["status"], "spool_id": spool_id, "grams": grams},
        headers=CSRF,
    )


def change_hold(
    user: TestClient, read: dict[str, Any], hold_id: int, spool_id: int, grams: int
) -> Response:
    return user.put(
        f"{REQUESTS}/{read['id']}/holds/{hold_id}",
        json={"from_status": read["status"], "spool_id": spool_id, "grams": grams},
        headers=CSRF,
    )


def remove_hold(user: TestClient, read: dict[str, Any], hold_id: int) -> Response:
    return user.delete(
        f"{REQUESTS}/{read['id']}/holds/{hold_id}",
        params={"from_status": read["status"]},
        headers=CSRF,
    )


def _hold_id(read: dict[str, Any]) -> int:
    [hold] = _choice(read)["holds"]
    return hold["id"]


def _released(app: FastAPI) -> list[tuple[int, int, ReleaseReason | None]]:
    with app.state.session_factory() as session:
        query = select(SpoolHold).where(SpoolHold.released_at.is_not(None))
        return [(h.spool_id, h.grams, h.release_reason) for h in session.scalars(query)]


# --- Holds by hand ----------------------------------------------------------------------------


def test_a_hold_on_a_similar_colors_spool_queues_a_waiting_request_it_covers(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    charcoal = stock(client, token, CHARCOAL_PLA, "PLA", "received")
    waiting = _approved(sam, frank, pla, 1500)
    [(black_spool, _)] = _holds(waiting)

    response = add_hold(frank, waiting, _spool(client, charcoal), 500)

    assert response.status_code == 200, response.text
    read = response.json()
    assert read["status"] == "queued"
    assert [(h["spool_id"], h["product_id"], h["grams"]) for h in _choice(read)["holds"]] == [
        (black_spool, pla, 1000),
        (_spool(client, charcoal), charcoal, 500),
    ]
    assert [e["kind"] for e in read["history"][:2]] == ["status_changed", "holds_changed"]


def test_swapping_a_hold_to_another_spool_releases_the_old_one_as_changed(
    app: FastAPI, client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    charcoal = stock(client, token, CHARCOAL_PLA, "PLA", "received")
    queued = _approved(sam, frank, pla, 300)
    assert queued["status"] == "queued"
    black_spool, charcoal_spool = _spool(client, pla), _spool(client, charcoal)

    response = change_hold(frank, queued, _hold_id(queued), charcoal_spool, 300)

    assert response.status_code == 200, response.text
    read = response.json()
    assert (read["status"], _holds(read)) == ("queued", [(charcoal_spool, 300)])
    assert _released(app) == [(black_spool, 300, ReleaseReason.CHANGED)]
    assert read["history"][0]["kind"] == "holds_changed"


def test_a_queued_request_left_short_stays_queued_and_shows_what_it_is_short(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    queued = _approved(sam, frank, pla, 300)
    spool_id = _spool(client, pla)

    lowered = change_hold(frank, queued, _hold_id(queued), spool_id, 100).json()

    assert (lowered["status"], _holds(lowered), _choice(lowered)["short_g"]) == (
        "queued",
        [(spool_id, 100)],
        200,
    )
    removed = remove_hold(frank, lowered, _hold_id(lowered))
    assert removed.status_code == 200, removed.text
    read = removed.json()
    assert (read["status"], _holds(read), _choice(read)["short_g"]) == ("queued", [], 300)
    assert [e["kind"] for e in read["history"][:2]] == ["holds_changed", "holds_changed"]


def test_a_hold_by_hand_takes_no_more_than_the_spool_has_free_and_only_a_spool_on_the_shelf(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    gone = stock(client, token, CHARCOAL_PLA, "PLA", "received", "opened", "empty")
    queued = _approved(sam, frank, pla, 300)
    spool_id = _spool(client, pla)

    too_much = add_hold(frank, queued, spool_id, 701)
    empty = add_hold(frank, queued, _spool(client, gone), 10)
    none = add_hold(frank, queued, spool_id, 0)

    assert (too_much.status_code, too_much.json()["detail"]["problems"]) == (
        422,
        {"grams": "This spool has about 700 g free."},
    )
    assert (empty.status_code, empty.json()["detail"]["problems"]) == (
        422,
        {"spool_id": "Choose a Sealed or Open spool."},
    )
    assert (none.status_code, none.json()["detail"]["problems"]) == (
        422,
        {"grams": "Grams must be 1 to 100,000."},
    )
    assert _holds(_read(frank, queued["id"])) == [(spool_id, 300)]
    assert add_hold(frank, queued, spool_id, 700).status_code == 200


@pytest.mark.parametrize("status", ["submitted", "printing", "done", "failed", "cancelled"])
def test_holds_change_only_while_approved_waiting_or_queued(
    client: TestClient, token: str, sam: TestClient, frank: TestClient, status: str
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    queued = _approved(sam, frank, pla, 300)
    hold_id, spool_id = _hold_id(queued), _spool(client, pla)
    put_in(frank, queued["id"], status)
    read = _read(frank, queued["id"])

    for response in (
        set_grams(frank, read, 200),
        add_hold(frank, read, spool_id, 10),
        change_hold(frank, read, hold_id, spool_id, 10),
        remove_hold(frank, read, hold_id),
    ):
        assert (response.status_code, response.json()["detail"]) == (403, NOT_NOW)
    assert read["can_change_holds"] is False


def test_a_change_to_a_request_that_has_moved_on_answers_409_and_saves_nothing(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    queued = _approved(sam, frank, pla, 300)
    hold_id, spool_id = _hold_id(queued), _spool(client, pla)
    stale = {**queued, "status": "waiting_on_filament"}

    for response in (
        set_grams(frank, stale, 200),
        add_hold(frank, stale, spool_id, 10),
        change_hold(frank, stale, hold_id, spool_id, 10),
        remove_hold(frank, stale, hold_id),
    ):
        assert (response.status_code, response.json()["detail"]) == (409, STALE)
    assert remove_hold(frank, queued, hold_id).status_code == 200
    # The hold was changed meanwhile, on a page that still shows it.
    assert remove_hold(frank, queued, hold_id).status_code == 409
    assert _read(frank, queued["id"])["history"][0]["kind"] == "holds_changed"


def test_another_requests_choice_or_hold_is_not_found(
    client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    mine, theirs = _approved(sam, frank, pla, 100), _approved(sam, frank, pla, 100)
    elsewhere = {**mine, "choices": theirs["choices"]}

    assert set_grams(frank, elsewhere, 50).status_code == 404
    assert add_hold(frank, elsewhere, _spool(client, pla), 50).status_code == 404
    assert change_hold(frank, mine, _hold_id(theirs), _spool(client, pla), 50).status_code == 404
    assert remove_hold(frank, mine, 9999).status_code == 404


def test_hold_changes_send_no_email(
    app: FastAPI,
    client: TestClient,
    token: str,
    sam: TestClient,
    frank: TestClient,
    outbox: FakeOutbox,
) -> None:
    email_on(client)
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    waiting = _approved(sam, frank, pla, 1500)
    sent(app, outbox)

    read = set_grams(frank, waiting, 800).json()
    read = change_hold(frank, read, _hold_id(read), _spool(client, pla), 900).json()
    remove_hold(frank, read, _hold_id(read))

    assert sent(app, outbox) == []


# --- Who may change holds ---------------------------------------------------------------------


def test_only_an_admin_is_offered_hold_changes(
    app: FastAPI, client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    queued = _approved(sam, frank, pla, 300)
    eddie = person(app, "eddie", Role.EDITOR)

    assert frank.get(f"{REQUESTS}/{queued['id']}").json()["can_change_holds"] is True
    for user in (eddie, sam):
        assert user.get(f"{REQUESTS}/{queued['id']}").json()["can_change_holds"] is False


def test_editors_and_requesters_are_refused_and_requesters_see_the_change(
    app: FastAPI, client: TestClient, token: str, sam: TestClient, frank: TestClient
) -> None:
    pla = stock(client, token, BLACK_PLA, "PLA", "received")
    queued = _approved(sam, frank, pla, 300)
    eddie = person(app, "eddie", Role.EDITOR)

    for user in (eddie, sam):
        assert set_grams(user, queued, 200).status_code == 403
        assert remove_hold(user, queued, _hold_id(queued)).status_code == 403
    assert set_grams(frank, queued, 200).status_code == 200

    entry = _read(sam, queued["id"])["history"][0]
    assert (entry["kind"], entry["username"]) == ("holds_changed", "frank")
