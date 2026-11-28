import pytest
from fastapi.testclient import TestClient

from filament_tracker.main import create_app

COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture(autouse=True)
def _no_build_info(monkeypatch: pytest.MonkeyPatch) -> None:
    # A test run is a development build unless a test says otherwise.
    monkeypatch.delenv("ROLLCALL_VERSION", raising=False)
    monkeypatch.delenv("ROLLCALL_COMMIT", raising=False)


def test_health_is_ok_without_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "dev",
        "home_assistant": {"mqtt": "off", "events": "off"},
    }


def test_health_exists_only_under_the_versioned_prefix() -> None:
    client = TestClient(create_app())

    assert client.get("/health").status_code == 404


@pytest.mark.parametrize("version", ["1.4.0", "1.4.0-rc.1"])
def test_health_reports_the_version_the_image_was_built_with(
    monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    monkeypatch.setenv("ROLLCALL_VERSION", version)
    monkeypatch.setenv("ROLLCALL_COMMIT", COMMIT)

    health = TestClient(create_app()).get("/api/v1/health").json()

    assert health["version"] == version


def test_a_build_with_only_a_commit_reports_dev_and_the_short_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLLCALL_VERSION", "")
    monkeypatch.setenv("ROLLCALL_COMMIT", COMMIT)

    health = TestClient(create_app()).get("/api/v1/health").json()

    assert health["version"] == "dev (0123456)"


def test_a_build_with_neither_reports_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROLLCALL_VERSION", "")
    monkeypatch.setenv("ROLLCALL_COMMIT", "")

    health = TestClient(create_app()).get("/api/v1/health").json()

    assert health["version"] == "dev"
