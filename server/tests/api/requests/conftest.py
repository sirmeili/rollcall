"""Print request tests: the server with the catalog faked (as in the catalog tests), so
filament choices can name catalog colors, and a model-file directory per test."""

import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fake_outbox import FakeOutbox
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# The catalog tests' fakes of OFDB and BambuStudio's list.
sys.path.insert(0, str(Path(__file__).parent.parent / "catalog"))

from api_helpers import ADMIN_TOKEN, BASE_URL, LAN_CLIENT, register  # noqa: E402
from bambustudio_fake import BAMBUSTUDIO_ETAG, body, color_codes  # noqa: E402
from ofdb_fake import FakeSource, ok, refresh  # noqa: E402

from filament_tracker.config import Settings  # noqa: E402
from filament_tracker.main import create_app  # noqa: E402


@pytest.fixture
def ofdb() -> FakeSource:
    return FakeSource()


@pytest.fixture
def outbox() -> FakeOutbox:
    """Where the server's emails go instead of a mail server."""
    return FakeOutbox()


@pytest.fixture
def app(db_url: str, ofdb: FakeSource, outbox: FakeOutbox) -> FastAPI:
    settings = Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None)
    bambustudio = FakeSource(ok(body(color_codes()), etag=BAMBUSTUDIO_ETAG))

    def route(request: httpx.Request) -> httpx.Response:
        source = bambustudio if request.url.host == "raw.githubusercontent.com" else ofdb
        return source.handle(request)

    return create_app(settings, catalog_transport=httpx.MockTransport(route), mail_transport=outbox)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        refresh(client)
        yield client


@pytest.fixture
def token(client: TestClient) -> str:
    return register(client)


@pytest.fixture
def db(app: FastAPI, client: TestClient) -> Iterator[Session]:
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def files_dir(db_url: str) -> Path:
    """Where the server keeps model files: beside the database."""
    return Path(db_url.removeprefix("sqlite:///")).parent / "request-files"
