"""The Phone notifications settings group: Firebase, for phone notifications through Google's
official push service (FCM). Admin only, with `.env` as the fallback (ADR-0007)."""

from typing import Any

from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from fake_push_outbox import FIREBASE, FakePushOutbox, service_account
from fastapi.testclient import TestClient
from pydantic import SecretStr

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

URL = "/api/v1/settings/phone-notifications"


def by_key(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in body["settings"]}


def save(client: TestClient, values: dict[str, str]) -> Any:
    return client.put(URL, json={"values": values}, headers=admin())


def test_the_phone_notifications_group_starts_empty(client: TestClient) -> None:
    response = client.get(URL, headers=admin())

    assert response.status_code == 200
    settings = by_key(response.json())
    assert list(settings) == [
        "firebase_project_id",
        "firebase_app_id",
        "firebase_api_key",
        "firebase_sender_id",
        "firebase_service_account",
    ]
    assert all(not s["set"] for s in settings.values())
    assert settings["firebase_service_account"]["secret"] is True
    assert not any(s["secret"] for k, s in settings.items() if k != "firebase_service_account")


def test_an_admin_saves_firebase_and_the_key_reads_back_only_as_set(client: TestClient) -> None:
    key = service_account().json

    response = save(client, {**FIREBASE, "firebase_service_account": key})

    assert response.status_code == 200, response.text
    settings = by_key(response.json())
    assert settings["firebase_project_id"]["value"] == FIREBASE["firebase_project_id"]
    assert settings["firebase_sender_id"]["value"] == FIREBASE["firebase_sender_id"]
    account = settings["firebase_service_account"]
    assert account == {**account, "value": None, "set": True, "source": "app"}
    assert "PRIVATE KEY" not in response.text


def test_environment_variables_are_the_fallback(db_url: str) -> None:
    key = service_account().json
    settings = Settings(
        database_url=db_url,
        admin_token=ADMIN_TOKEN,
        firebase_project_id="rollcall-env",
        firebase_service_account=SecretStr(key),
        _env_file=None,
    )
    app = create_app(settings, push_transport=FakePushOutbox())
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        settings_out = by_key(client.get(URL, headers=admin()).json())

        saved = save(client, {"firebase_project_id": "rollcall-app"})
        after = by_key(saved.json())

    assert settings_out["firebase_project_id"] == {
        **settings_out["firebase_project_id"],
        "value": "rollcall-env",
        "source": "env",
    }
    assert settings_out["firebase_service_account"]["source"] == "env"
    assert settings_out["firebase_service_account"]["value"] is None
    assert after["firebase_project_id"]["value"] == "rollcall-app"


def test_a_key_that_isnt_a_service_account_key_is_refused_without_repeating_it(
    client: TestClient,
) -> None:
    not_json = save(client, {"firebase_service_account": "not-a-key-but-secret-text"})
    no_private_key = save(client, {"firebase_service_account": '{"type": "service_account"}'})

    assert not_json.status_code == 422
    assert "not-a-key-but-secret-text" not in not_json.text
    assert no_private_key.status_code == 422


def test_a_whole_service_account_key_fits(client: TestClient) -> None:
    key = service_account().json
    assert len(key) > 1024

    assert save(client, {"firebase_service_account": key}).status_code == 200


def test_ids_are_checked(client: TestClient) -> None:
    response = save(
        client,
        {
            "firebase_project_id": "Not A Project",
            "firebase_app_id": "app",
            "firebase_api_key": "key with spaces",
            "firebase_sender_id": "12ab",
        },
    )

    assert response.status_code == 422
    assert set(response.json()["detail"]["problems"]) == {
        "firebase_project_id",
        "firebase_app_id",
        "firebase_api_key",
        "firebase_sender_id",
    }


def test_only_an_admin_reads_or_saves_them(app: Any, client: TestClient) -> None:
    editor = signed_in(app, Role.EDITOR)

    assert editor.get(URL).status_code == 403
    assert editor.put(URL, json={"values": FIREBASE}, headers=CSRF).status_code == 403
