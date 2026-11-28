"""Security suite for M2: the role on every route, the CSRF header, bearer tokens only from
the LAN (with and without a reverse proxy), LAN-only API docs and security headers."""

import re
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from api_helpers import (
    ADMIN_TOKEN,
    BASE_URL,
    CSRF,
    INTERNET_CLIENT,
    REQUEST_ROUTES,
    admin,
    bearer,
    browser,
    scan,
    scan_body,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.config import Settings
from filament_tracker.db.models import Event
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import EventSource, Role
from filament_tracker.main import create_app

# Every route that needs a role, and the lowest role allowed.
ROUTES = [
    ("get", "/api/v1/inventory", Role.VIEWER),
    ("get", "/api/v1/products", Role.VIEWER),
    ("get", "/api/v1/products/99", Role.VIEWER),
    ("get", "/api/v1/spools", Role.VIEWER),
    ("get", "/api/v1/spools/99", Role.VIEWER),
    ("get", "/api/v1/events", Role.VIEWER),
    ("get", "/api/v1/review", Role.VIEWER),
    ("get", "/api/v1/catalog", Role.VIEWER),
    ("get", "/api/v1/catalog/sync", Role.ADMIN),
    ("post", "/api/v1/catalog/sync", Role.ADMIN),
    ("get", "/api/v1/shopping-list", Role.VIEWER),
    ("post", "/api/v1/shopping-list/hand-reasons", Role.EDITOR),
    ("delete", "/api/v1/shopping-list/hand-reasons/99", Role.EDITOR),
    ("post", "/api/v1/shopping-list/items/99/ordered", Role.EDITOR),
    ("put", "/api/v1/shopping-list/items/99/on-order", Role.EDITOR),
    ("post", "/api/v1/shopping-list/items/99/dismiss", Role.EDITOR),
    ("post", "/api/v1/shopping-list/items/99/bring-back", Role.EDITOR),
    ("post", "/api/v1/shopping-list/suggestions", Role.VIEWER),
    ("post", "/api/v1/shopping-list/suggestions/99/add", Role.EDITOR),
    ("post", "/api/v1/shopping-list/suggestions/99/dismiss", Role.EDITOR),
    ("put", "/api/v1/shopping-list/items/99/size", Role.EDITOR),
    ("patch", "/api/v1/spools/99", Role.EDITOR),
    ("patch", "/api/v1/spools", Role.EDITOR),
    ("post", "/api/v1/spools", Role.EDITOR),
    ("post", "/api/v1/spools/99/events", Role.EDITOR),
    ("post", "/api/v1/products", Role.EDITOR),
    ("patch", "/api/v1/products/99", Role.EDITOR),
    ("post", f"/api/v1/review/events/{uuid4()}/accept", Role.EDITOR),
    ("post", "/api/v1/review/tags/DEADBEEF/dismiss", Role.EDITOR),
    ("post", f"/api/v1/review/events/{uuid4()}/unaccept", Role.EDITOR),
    ("post", "/api/v1/review/tags/DEADBEEF/restore", Role.EDITOR),
    ("post", "/api/v1/review/spools/99/dismiss", Role.EDITOR),
    ("post", "/api/v1/review/spools/99/restore", Role.EDITOR),
    ("post", "/api/v1/review/duplicates/99/same-product", Role.EDITOR),
    ("post", "/api/v1/review/duplicates/99/keep-separate", Role.EDITOR),
    ("post", "/api/v1/review/duplicates/99/restore", Role.EDITOR),
    ("get", "/api/v1/printers", Role.ADMIN),
    ("post", "/api/v1/printers/99/unpin", Role.ADMIN),
    ("post", "/api/v1/printers", Role.ADMIN),
    ("patch", "/api/v1/printers/99", Role.ADMIN),
    ("delete", "/api/v1/printers/99", Role.ADMIN),
    ("post", "/api/v1/printers/99/test", Role.ADMIN),
    ("get", "/api/v1/settings/general", Role.ADMIN),
    ("put", "/api/v1/settings/scanners", Role.ADMIN),
    ("get", "/api/v1/settings/catalog", Role.ADMIN),
    ("put", "/api/v1/settings/catalog", Role.ADMIN),
    ("post", "/api/v1/devices/scanner-9/rotate", Role.ADMIN),
    ("get", "/api/v1/devices", Role.ADMIN),
    ("post", "/api/v1/devices", Role.ADMIN),
    ("post", "/api/v1/devices/scanner-9/revoke", Role.ADMIN),
    ("delete", "/api/v1/devices/scanner-9", Role.ADMIN),
    ("get", "/api/v1/tokens", Role.ADMIN),
    ("post", "/api/v1/tokens", Role.ADMIN),
    ("delete", "/api/v1/tokens/99", Role.ADMIN),
    ("get", "/api/v1/users", Role.ADMIN),
    ("post", "/api/v1/users", Role.ADMIN),
    ("patch", "/api/v1/users/99", Role.ADMIN),
    ("get", "/api/v1/settings/home-assistant", Role.ADMIN),
    ("put", "/api/v1/settings/home-assistant", Role.ADMIN),
    ("delete", "/api/v1/settings/home-assistant/ha_url", Role.ADMIN),
    ("post", "/api/v1/settings/home-assistant/test", Role.ADMIN),
    ("get", "/api/v1/settings/email", Role.ADMIN),
    ("put", "/api/v1/settings/email", Role.ADMIN),
    ("delete", "/api/v1/settings/email/smtp_host", Role.ADMIN),
    ("get", "/api/v1/settings/email/status", Role.ADMIN),
    ("post", f"/api/v1/events/{uuid4()}/revert", Role.EDITOR),
]


# Routes only a signed-in user can use, never a token, and the lowest role allowed.
USER_ROUTES = [
    ("patch", "/api/v1/auth/me", Role.VIEWER),
    ("post", "/api/v1/settings/email/test", Role.ADMIN),
    ("get", "/api/v1/push/config", Role.VIEWER),
    ("put", "/api/v1/push/devices/phone-9", Role.VIEWER),
    ("delete", "/api/v1/push/devices/phone-9", Role.VIEWER),
    ("post", "/api/v1/push/devices/phone-9/test", Role.VIEWER),
]

# A scanner's token reaches only the scanner routes and an undo of its own scan.
NOT_SCANNER_ROUTES = [(m, path) for m, path, _ in ROUTES if not path.endswith("/revert")]


# Every other route the app serves, as the app names it, and why it is not in the lists above
# or REQUEST_ROUTES.
EXEMPT = [
    # Open to anyone.
    ("get", "/api/v1/health"),
    ("get", "/api/v1/setup"),
    ("post", "/api/v1/setup"),
    # Signing in and out, and the signed-in user's own account.
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/logout"),
    ("get", "/api/v1/auth/me"),
    ("post", "/api/v1/auth/password"),
    # For scanners only (test_security.py, test_devices.py).
    ("post", "/api/v1/scans"),
    ("post", "/api/v1/devices/heartbeat"),
    ("post", "/api/v1/devices/unlink"),
    ("get", "/api/v1/devices/provisioning"),
    # A signed-in user registering their own phone.
    ("post", "/api/v1/devices/mine"),
]


def _call(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None):  # noqa: ANN202
    if method in ("post", "patch", "put"):
        return client.request(method.upper(), path, json={}, headers=headers)
    return client.request(method.upper(), path, headers=headers)


def _template_of(method: str, path: str, served: set[tuple[str, str]]) -> tuple[str, str]:
    """The served route a request in the lists above reaches, ignoring its query (a literal one
    over one with a parameter in the same place, as the app picks it)."""
    path = path.split("?")[0]
    matches = [
        (m, template)
        for m, template in served
        if m == method and re.fullmatch(re.sub(r"\{[^/]+\}", "[^/]+", template), path)
    ]
    assert matches, f"{method} {path} is not a route the app serves"
    return min(matches, key=lambda route: route[1].count("{"))


def test_every_served_route_is_in_the_matrix_or_exempt(app: FastAPI) -> None:
    served = {(m, path) for path, ops in app.openapi()["paths"].items() for m in ops}

    listed = {_template_of(m, path, served) for m, path, _ in ROUTES + USER_ROUTES + REQUEST_ROUTES}

    assert served - listed - set(EXEMPT) == set()  # a new route needs a row above
    assert set(EXEMPT) - served == set()  # and an exempt route the app no longer serves goes


@pytest.mark.parametrize(("method", "path"), [(m, path) for m, path, _ in ROUTES])
def test_each_route_refuses_no_credentials(client: TestClient, method: str, path: str) -> None:
    assert _call(client, method, path).status_code == 401


@pytest.mark.parametrize(("method", "path"), NOT_SCANNER_ROUTES)
def test_each_route_refuses_a_scanner(
    client: TestClient, token: str, method: str, path: str
) -> None:
    assert _call(client, method, path, bearer(token)).status_code == 403


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES)
@pytest.mark.parametrize("role", list(Role))
def test_each_route_needs_its_role(
    app: FastAPI, client: TestClient, method: str, path: str, needed: Role, role: Role
) -> None:
    user = signed_in(app, role)

    status = _call(user, method, path, CSRF).status_code

    if role.allows(needed):
        assert status not in (401, 403)
    else:
        assert status == 403


@pytest.mark.parametrize(("method", "path", "needed"), USER_ROUTES)
@pytest.mark.parametrize("role", list(Role))
def test_each_signed_in_route_needs_its_role(
    app: FastAPI, client: TestClient, method: str, path: str, needed: Role, role: Role
) -> None:
    user = signed_in(app, role)

    status = _call(user, method, path, CSRF).status_code

    if role.allows(needed):
        assert status not in (401, 403)
    else:
        assert status == 403


@pytest.mark.parametrize(("method", "path", "needed"), USER_ROUTES)
def test_signed_in_routes_refuse_every_token(
    client: TestClient, method: str, path: str, needed: Role
) -> None:
    made = client.post(
        "/api/v1/tokens", json={"name": "Script", "role": "admin"}, headers=admin()
    ).json()

    assert _call(client, method, path, admin()).status_code == 403
    assert _call(client, method, path, bearer(made["token"])).status_code == 403
    assert _call(client, method, path).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "needed"), [r for r in ROUTES if r[2] in (Role.EDITOR, Role.ADMIN)]
)
def test_requester_gains_no_editor_or_admin_route(
    app: FastAPI, client: TestClient, method: str, path: str, needed: Role
) -> None:
    requester = signed_in(app, Role.VIEWER, requester=True)

    assert _call(requester, method, path, CSRF).status_code == 403


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES + USER_ROUTES)
def test_cookie_writes_need_the_csrf_header(
    app: FastAPI, client: TestClient, method: str, path: str, needed: Role
) -> None:
    user = signed_in(app, Role.ADMIN)

    response = _call(user, method, path)

    if method == "get":
        assert response.status_code in (200, 404)  # reads need no header
    else:
        assert response.status_code == 403
        assert "x-requested-with" in response.json()["detail"]


def test_the_csrf_header_must_have_the_right_value(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.ADMIN)

    response = user.post("/api/v1/users", json={}, headers={"X-Requested-With": "XMLHttpRequest"})

    assert response.status_code == 403


def test_bearer_requests_do_not_need_the_csrf_header(client: TestClient) -> None:
    assert client.get("/api/v1/users", headers=admin()).status_code == 200
    assert client.post("/api/v1/users", json={}, headers=admin()).status_code == 422


def test_an_editor_undo_records_who_did_it(
    app: FastAPI, client: TestClient, token: str, db: Session
) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    editor = signed_in(app, Role.EDITOR)

    response = editor.post(f"/api/v1/events/{received['event_id']}/revert", headers=CSRF)

    assert response.status_code == 200
    revert = db.get(Event, UUID(response.json()["revert_event_id"]))
    assert revert.user_id == 1
    assert revert.source == EventSource.UI
    assert revert.device_id is None


def test_an_admin_token_undo_has_no_user(client: TestClient, token: str, db: Session) -> None:
    received = scan(client, token, SyntheticTag(), "received")

    response = client.post(f"/api/v1/events/{received['event_id']}/revert", headers=admin())

    assert db.get(Event, UUID(response.json()["revert_event_id"])).user_id is None


# --- Bearer tokens only from the LAN -------------------------------------------------------


def test_tokens_are_refused_from_the_internet(app: FastAPI, client: TestClient, token: str) -> None:
    outside = browser(app, INTERNET_CLIENT)
    body = scan_body(SyntheticTag(), "lookup")

    assert outside.post("/api/v1/scans", json=body, headers=bearer(token)).status_code == 403
    assert outside.get("/api/v1/devices", headers=admin()).status_code == 403


def test_sessions_work_from_the_internet(app: FastAPI, client: TestClient) -> None:
    outside = signed_in(app, Role.ADMIN, client=INTERNET_CLIENT)

    assert outside.get("/api/v1/users").status_code == 200


def test_a_client_cannot_claim_a_lan_address(app: FastAPI, client: TestClient) -> None:
    outside = browser(app, INTERNET_CLIENT)

    response = outside.get(
        "/api/v1/devices", headers={**admin(), "X-Forwarded-For": "192.168.1.20"}
    )

    assert response.status_code == 403


PROXY = ("192.168.1.5", 40000)


@pytest.fixture
def proxied_app(db_url: str) -> Iterator[FastAPI]:
    settings = Settings(
        database_url=db_url,
        admin_token=ADMIN_TOKEN,
        forwarded_allow_ips="192.168.1.5",
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app, base_url=BASE_URL, client=PROXY):
        yield app


@pytest.mark.parametrize(
    ("forwarded", "expected"),
    [
        ("203.0.113.7", 403),  # an internet client through the proxy
        ("192.168.1.30", 200),  # a LAN client through the proxy
        ("192.168.1.30, 203.0.113.7", 403),  # a spoofed LAN address, appended to by the proxy
        ("not-an-ip", 403),
    ],
)
def test_behind_the_proxy_the_forwarded_address_counts(
    proxied_app: FastAPI, forwarded: str, expected: int
) -> None:
    via_proxy = TestClient(proxied_app, base_url=BASE_URL, client=PROXY)

    response = via_proxy.get("/api/v1/devices", headers={**admin(), "X-Forwarded-For": forwarded})

    assert response.status_code == expected


def test_throttling_uses_the_forwarded_address(proxied_app: FastAPI) -> None:
    via_proxy = TestClient(proxied_app, base_url=BASE_URL, client=PROXY)

    def attempt(address: str, username: str) -> int:
        return via_proxy.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong password!"},
            headers={**CSRF, "X-Forwarded-For": address},
        ).status_code

    for n in range(20):
        attempt("203.0.113.7", f"user{n}")

    assert attempt("203.0.113.7", "fresh") == 429
    assert attempt("203.0.113.8", "fresh") == 401


# --- API docs and headers ------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_lan_only(app: FastAPI, client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200
    assert browser(app, INTERNET_CLIENT).get(path).status_code == 404


def test_security_headers_are_on_every_response(client: TestClient) -> None:
    for response in (
        client.get("/api/v1/health"),
        client.get("/api/v1/devices"),
        client.post("/api/v1/scans", content=b"x" * 20_000),
    ):
        headers = response.headers
        assert headers["x-frame-options"] == "DENY"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert "script-src 'self';" in headers["content-security-policy"]


def test_the_docs_get_a_policy_that_allows_their_cdn(client: TestClient) -> None:
    policy = client.get("/docs").headers["content-security-policy"]

    assert "https://cdn.jsdelivr.net" in policy
    assert "frame-ancestors 'none'" in policy
