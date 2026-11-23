"""Phone notification tests: the server with its Web Pushes going to a fake push outbox and its
emails to a fake outbox, and the catalog faked as in the print request tests, so requests can
be submitted with their helpers."""

import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fake_outbox import FakeOutbox
from fake_push_outbox import FakePushOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "requests"))
sys.path.insert(0, str(Path(__file__).parent.parent / "catalog"))

from api_helpers import ADMIN_TOKEN, BASE_URL, LAN_CLIENT  # noqa: E402
from bambustudio_fake import BAMBUSTUDIO_ETAG, body, color_codes  # noqa: E402
from ofdb_fake import FakeSource, ok, refresh  # noqa: E402

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
    ofdb = FakeSource()
    bambustudio = FakeSource(ok(body(color_codes()), etag=BAMBUSTUDIO_ETAG))

    def route(request: httpx.Request) -> httpx.Response:
        source = bambustudio if request.url.host == "raw.githubusercontent.com" else ofdb
        return source.handle(request)

    return create_app(
        settings,
        catalog_transport=httpx.MockTransport(route),
        mail_transport=outbox,
        push_transport=pushes,
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        refresh(client)
        yield client
