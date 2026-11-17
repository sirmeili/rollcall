"""The server with OFDB and BambuStudio's list faked, for every catalog test: nothing
contacts the internet."""

from collections.abc import Iterator

import httpx
import pytest
from api_helpers import ADMIN_TOKEN, BASE_URL, LAN_CLIENT, register
from bambustudio_fake import BAMBUSTUDIO_ETAG, body, color_codes
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, ok
from sqlalchemy.orm import Session

from filament_tracker.config import Settings
from filament_tracker.main import create_app


@pytest.fixture
def ofdb() -> FakeSource:
    return FakeSource()


@pytest.fixture
def bambustudio() -> FakeSource:
    return FakeSource(ok(body(color_codes()), etag=BAMBUSTUDIO_ETAG))


@pytest.fixture
def app(db_url: str, ofdb: FakeSource, bambustudio: FakeSource) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)

    def route(request: httpx.Request) -> httpx.Response:
        source = bambustudio if request.url.host == "raw.githubusercontent.com" else ofdb
        return source.handle(request)

    return create_app(settings, catalog_transport=httpx.MockTransport(route))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        yield client


@pytest.fixture
def token(client: TestClient) -> str:
    return register(client)


@pytest.fixture
def db(app: FastAPI, client: TestClient) -> Iterator[Session]:
    with app.state.session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def catalog_sync_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The catalog's settings at their defaults; OFDB is faked here (see `app`)."""
    monkeypatch.delenv("CATALOG_SYNC", raising=False)
