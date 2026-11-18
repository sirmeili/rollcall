"""Submitting a print request, and reading it back."""

from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import JADE_WHITE, REQUESTS, person, stock, submit, submitted

from filament_tracker.domain.enums import Role


def test_a_requester_submits_a_request_and_reads_it_back(
    app: FastAPI, client: TestClient, token: str
) -> None:
    product = stock(client, token, "0A2CA5FF", "PLA", "received")
    sam = person(app, "sam")
    needed = (date.today() + timedelta(days=7)).isoformat()

    created = submitted(
        sam,
        title="  Board game insert  ",
        notes="The version with the egg tray.",
        quantity=3,
        needed_by=needed,
        priority="urgent",
        choices=[
            {"product_id": product, "note": "main body"},
            {"catalog_color": JADE_WHITE, "note": "accents"},
        ],
    )

    read = sam.get(f"{REQUESTS}/{created['id']}").json()
    assert read == created
    assert read["title"] == "Board game insert"
    assert read["notes"] == "The version with the egg tray."
    assert (read["quantity"], read["needed_by"], read["priority"]) == (3, needed, "urgent")
    assert read["link"] == "https://makerworld.com/en/models/412877"
    assert read["status"] == "submitted"
    assert read["requester"] == {"id": 1, "username": "sam"}
    assert read["file"] is None
    assert [(c["kind"], c["note"]) for c in read["choices"]] == [
        ("product", "main body"),
        ("catalog_color", "accents"),
    ]


def test_the_defaults_are_one_copy_at_normal_priority(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")
    body = {
        "title": "Clips",
        "link": "https://www.printables.com/model/1",
        "choices": [{"catalog_color": JADE_WHITE}],
    }

    created = sam.post(REQUESTS, json=body, headers={"X-Requested-With": "filament-tracker"})

    assert created.status_code == 201, created.text
    assert (created.json()["quantity"], created.json()["priority"]) == (1, "normal")
    assert created.json()["needed_by"] is None


def test_submitting_writes_the_first_history_entry(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")

    history = submitted(sam)["history"]

    assert [(h["kind"], h["username"]) for h in history] == [("submitted", "sam")]
    assert history[0]["at"] is not None


def test_me_says_a_requester_has_requests_once_they_submit(
    app: FastAPI, client: TestClient
) -> None:
    sam = person(app, "sam")
    assert sam.get("/api/v1/auth/me").json()["has_requests"] is False

    submitted(sam)

    assert sam.get("/api/v1/auth/me").json()["has_requests"] is True


def test_an_editor_or_admin_who_is_a_requester_submits_too(
    app: FastAPI, client: TestClient
) -> None:
    for role in (Role.EDITOR, Role.ADMIN):
        user = person(app, f"{role.value}-sam", role)
        assert submit(user).status_code == 201


def test_without_requester_nobody_submits(app: FastAPI, client: TestClient) -> None:
    for role in Role:
        user = person(app, f"{role.value}-plain", role, requester=False)
        assert submit(user).status_code == 403
