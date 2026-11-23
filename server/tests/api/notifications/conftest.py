"""Notification tests outside Print Requests: the server with its emails going to a fake
outbox, and the request email tests' helpers for email set up and the emails sent."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fake_outbox import FakeOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "requests"))

from api_helpers import ADMIN_TOKEN, BASE_URL, LAN_CLIENT  # noqa: E402

from filament_tracker.config import Settings  # noqa: E402
from filament_tracker.main import create_app  # noqa: E402


@pytest.fixture
def outbox() -> FakeOutbox:
    """Where the server's emails go instead of a mail server."""
    return FakeOutbox()


@pytest.fixture
def app(db_url: str, outbox: FakeOutbox) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    return create_app(settings, mail_transport=outbox)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        yield client
