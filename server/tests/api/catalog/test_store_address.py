"""The Store address: the Bambu store that Find in store searches. Set on the Settings
page by Admins, checked to be an https address with no path, and used at once."""

from typing import Any

import pytest
from api_helpers import CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import Role

CATALOG = "/api/v1/catalog"
SETTINGS = "/api/v1/settings/catalog"


def store_address(client: TestClient) -> str:
    return client.get(CATALOG, headers=admin()).json()["store_address"]


def save(client: TestClient, value: str) -> Any:
    return client.put(SETTINGS, json={"values": {"store_address": value}}, headers=admin())


def test_the_store_address_defaults_to_the_us_store(client: TestClient) -> None:
    assert store_address(client) == "https://us.store.bambulab.com"
    setting = {s["key"]: s for s in client.get(SETTINGS, headers=admin()).json()["settings"]}
    assert setting["store_address"]["value"] == "https://us.store.bambulab.com"
    assert setting["store_address"]["source"] == "default"


def test_a_saved_store_address_is_used_at_once_without_its_trailing_slash(
    client: TestClient,
) -> None:
    assert save(client, "https://eu.store.bambulab.com/").status_code == 200

    assert store_address(client) == "https://eu.store.bambulab.com"


@pytest.mark.parametrize(
    "value",
    [
        "http://us.store.bambulab.com",
        "https://us.store.bambulab.com/search",
        "https://us.store.bambulab.com//",
        "https://us.store.bambulab.com?q=1",
        "https://us.store.bambulab.com#top",
        "https://me:pw@us.store.bambulab.com",
        "https://",
        "us.store.bambulab.com",
        "",
    ],
)
def test_the_store_address_takes_only_an_https_address_without_a_path(
    client: TestClient, value: str
) -> None:
    response = save(client, value)

    assert response.status_code == 422
    assert response.json()["detail"]["problems"]["store_address"] in (
        "Enter an https address with no path, like https://us.store.bambulab.com",
        "needs a value",
    )
    assert store_address(client) == "https://us.store.bambulab.com"


@pytest.mark.parametrize("role", [Role.VIEWER, Role.EDITOR])
def test_only_admins_see_or_change_the_store_address(
    app: FastAPI, client: TestClient, role: Role
) -> None:
    user = signed_in(app, role)

    assert user.get(SETTINGS).status_code == 403
    response = user.put(
        SETTINGS, json={"values": {"store_address": "https://eu.store.bambulab.com"}}, headers=CSRF
    )

    assert response.status_code == 403
    assert store_address(client) == "https://us.store.bambulab.com"
