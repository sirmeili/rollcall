"""Security suite for print requests (see docs/testing.md): every route refuses no
credentials, scanners and machine tokens below its role; uploads stop at 95 MB without the
whole body being read, on their route only; a model file is never served as something a
browser would run."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from api_helpers import CSRF, admin, bearer, register
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, person, request_body, submitted

from filament_tracker.domain.enums import Role
from filament_tracker.print_requests.files import MAX_MODEL_BYTES

UPLOADS = f"{REQUESTS}/uploads"
ROUTES = [
    ("get", REQUESTS, Role.EDITOR),
    ("post", REQUESTS, None),
    ("get", f"{REQUESTS}/count", Role.EDITOR),
    ("get", f"{REQUESTS}/1", Role.EDITOR),
    ("patch", f"{REQUESTS}/1", None),
    ("post", f"{REQUESTS}/1/priority", Role.EDITOR),
    ("post", f"{REQUESTS}/1/moves", Role.ADMIN),
    ("post", UPLOADS, None),
    ("get", f"{REQUESTS}/1/file", Role.EDITOR),
]


def _call(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None) -> Any:
    if method in ("post", "patch"):
        return client.request(method.upper(), path, json={}, headers=headers)
    return client.request(method.upper(), path, headers=headers)


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES)
def test_every_route_needs_credentials(
    client: TestClient, method: str, path: str, needed: Role | None
) -> None:
    assert _call(client, method, path).status_code == 401


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES)
def test_scanners_are_refused(
    client: TestClient, token: str, method: str, path: str, needed: Role | None
) -> None:
    assert _call(client, method, path, bearer(token)).status_code == 403


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES)
@pytest.mark.parametrize("role", list(Role))
def test_machine_tokens_act_only_with_their_role(
    client: TestClient, method: str, path: str, needed: Role | None, role: Role
) -> None:
    made = client.post("/api/v1/tokens", json={"name": "Script", "role": role}, headers=admin())

    status = _call(client, method, path, bearer(made.json()["token"])).status_code

    # A token is never a Requester; with a role that allows the route, it gets past the
    # check (to a 404 for a request that doesn't exist, or a 422 for an empty body).
    if needed is not None and role.allows(needed):
        assert status not in (401, 403)
    else:
        assert status == 403


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES)
def test_cookie_writes_need_the_csrf_header(
    app: FastAPI, client: TestClient, method: str, path: str, needed: Role | None
) -> None:
    sam = person(app, "sam", Role.ADMIN)
    if method == "get":
        pytest.skip("reads need no header")

    assert sam.request(method.upper(), path, json={}).status_code == 403


def test_another_users_request_reads_as_not_found_on_every_route(
    app: FastAPI, client: TestClient
) -> None:
    theirs = submitted(person(app, "maya"))["id"]
    sam = person(app, "sam")

    assert sam.get(f"{REQUESTS}/{theirs}").status_code == 404
    assert sam.get(f"{REQUESTS}/{theirs}/file").status_code == 404
    edit = sam.patch(f"{REQUESTS}/{theirs}", json=request_body(), headers=CSRF)
    assert edit.status_code == 404
    moved = sam.post(
        f"{REQUESTS}/{theirs}/moves",
        json={"from_status": "submitted", "to_status": "approved"},
        headers=CSRF,
    )
    assert moved.status_code == 404


# --- Uploads -------------------------------------------------------------------------------


class CountingBody:
    """A streamed body that counts how much of it was read."""

    def __init__(self, total: int, chunk: int = 1024 * 1024) -> None:
        self.total, self.chunk, self.sent = total, chunk, 0

    def __iter__(self) -> Iterator[bytes]:
        block = b"\0" * self.chunk
        while self.sent < self.total:
            size = min(self.chunk, self.total - self.sent)
            self.sent += size
            yield block[:size]


def _upload(user: TestClient, content: Any, **headers: str) -> Any:
    return user.post(
        UPLOADS,
        params={"name": "big.3mf"},
        content=content,
        headers={**CSRF, "Content-Type": "application/octet-stream", **headers},
    )


def test_an_upload_declared_over_95_mb_is_refused_before_it_is_read(
    app: FastAPI, client: TestClient
) -> None:
    sam = person(app, "sam")
    body = CountingBody(MAX_MODEL_BYTES + 1)

    response = _upload(sam, body, **{"Content-Length": str(MAX_MODEL_BYTES + 1)})

    assert response.status_code == 413
    assert body.sent < body.total


def test_a_streamed_upload_over_95_mb_is_cut_off_and_not_kept(
    app: FastAPI, client: TestClient, files_dir: Path
) -> None:
    sam = person(app, "sam")
    body = CountingBody(MAX_MODEL_BYTES + 3 * 1024 * 1024)

    response = _upload(sam, iter(body))

    assert response.status_code == 413
    assert list(files_dir.iterdir()) == []


def test_the_larger_limit_is_for_the_upload_route_only(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")
    big = request_body(notes="x" * 20_000)

    response = sam.post(REQUESTS, json=big, headers=CSRF)

    assert response.status_code == 413


def test_a_file_is_never_served_as_a_page(app: FastAPI, client: TestClient) -> None:
    sam = person(app, "sam")
    html = b"solid <html><script>alert(1)</script></html>"
    upload = sam.post(
        UPLOADS,
        params={"name": "page.html"},
        content=html,
        headers={**CSRF, "Content-Type": "text/html"},
    ).json()
    created = submitted(sam, upload_id=upload["id"])

    response = sam.get(f"{REQUESTS}/{created['id']}/file")

    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.fixture
def token(client: TestClient) -> str:
    return register(client)
