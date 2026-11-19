"""Helpers for print request tests: Requesters, stock on the shelf, and request bodies."""

from typing import Any

from api_helpers import CSRF, browser, login, make_user, scan
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

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
