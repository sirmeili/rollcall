"""Phone notification tests: the server with its Web Pushes going to a fake push outbox and its
emails to a fake outbox, and the request tests' helpers."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fake_outbox import FakeOutbox
from fake_push_outbox import FakePushOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "requests"))

from api_helpers import ADMIN_TOKEN, BASE_URL, LAN_CLIENT  # noqa: E402

from filament_tracker.config import Settings  # noqa: E402
from filament_tracker.main import create_app  # noqa: E402


@pytest.fixture
def outbox() -> FakeOutbox:
    return FakeOutbox()


@pytest.fixture
def pushes() -> FakePushOutbox:
    """Where the server's Web Pushes go instead of a push service."""
    return FakePushOutbox()


@pytest.fixture
def app(db_url: str, outbox: FakeOutbox, pushes: FakePushOutbox) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    return create_app(settings, mail_transport=outbox, push_transport=pushes)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        yield client
