"""Helpers for print request tests: Requesters, stock on the shelf, and request bodies."""

from typing import Any

from api_helpers import CSRF, browser, login, make_user, scan
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from filament_tracker.db.request_models import PrintRequest
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import RequestStatus, Role

REQUESTS = "/api/v1/requests"
# Catalog colors in the faked OFDB export.
BLACK = "var-black"
JADE_WHITE = "var-jade"
GRADIENT = "var-gradient"


def person(
    app: FastAPI, username: str, role: Role = Role.VIEWER, *, requester: bool = True
) -> TestClient:
    """A browser signed in as a new user."""
    make_user(app, username, role, requester=requester)
    user = browser(app)
    assert login(user, username).status_code == 200
    return user


def stock(client: TestClient, token: str, rgba: str, material: str, *actions: str) -> int:
    """One spool of a product, scanned through `actions`; the product's ID."""
    tag = SyntheticTag(
        color_rgba=rgba,
        filament_type=material,
        detailed_filament_type=material,
        material_id=f"GF{material[:3]}",
        variant_id=f"{material[:3]}-{rgba[:2]}",
    )
    result: dict[str, Any] = {}
    for action in actions:
        result = scan(client, token, tag, action)
    return result["product"]["id"]


def request_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Lithophane lamp shade",
        "notes": "",
        "quantity": 1,
        "needed_by": None,
        "priority": "normal",
        "link": "https://makerworld.com/en/models/412877",
        "choices": [{"catalog_color": JADE_WHITE, "note": ""}],
    }
    body.update(overrides)
    return body


def submit(user: TestClient, **overrides: Any) -> Response:
    return user.post(REQUESTS, json=request_body(**overrides), headers=CSRF)


def submitted(user: TestClient, **overrides: Any) -> dict[str, Any]:
    response = submit(user, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def edit(user: TestClient, request_id: int, **overrides: Any) -> Response:
    return user.patch(f"{REQUESTS}/{request_id}", json=request_body(**overrides), headers=CSRF)


def approve_body(request: dict[str, Any], grams: int = 10, note: str = "") -> dict[str, Any]:
    """Approve, with the same grams for every filament choice."""
    return {
        "from_status": "submitted",
        "to_status": "approved",
        "note": note,
        "grams": {str(choice["id"]): grams for choice in request["choices"]},
    }


def approve(user: TestClient, request: dict[str, Any], grams: int = 10, note: str = "") -> Response:
    """Approve with `grams` for every choice. With nothing in stock, it lands on Waiting on
    Filament."""
    return user.post(
        f"{REQUESTS}/{request['id']}/moves", json=approve_body(request, grams, note), headers=CSRF
    )


def move(
    user: TestClient, request_id: int, from_status: str, to_status: str, note: str = ""
) -> Response:
    """Move the request; Approve and Reprint give 10 g for every choice the user can see.
    With nothing in stock, Reprint lands on Waiting on Filament."""
    body: dict[str, Any] = {"from_status": from_status, "to_status": to_status, "note": note}
    if to_status == "approved" or (from_status, to_status) == ("failed", "queued"):
        choices = user.get(f"{REQUESTS}/{request_id}").json().get("choices", [])
        body["grams"] = {str(choice["id"]): 10 for choice in choices}
    return user.post(f"{REQUESTS}/{request_id}/moves", json=body, headers=CSRF)


def put_in(user: TestClient, request_id: int, status: str) -> None:
    """Put the request in `status` straight, as for Approved, which a request now passes
    through within Approve."""
    with user.app.state.session_factory() as session:  # type: ignore[attr-defined]
        session.get(PrintRequest, request_id).status = RequestStatus(status)
        session.commit()
