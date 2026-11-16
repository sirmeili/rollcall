"""A fake Open Filament Database for catalog tests: small exports, served through an injected
httpx transport, so OFDB is never contacted."""

import gzip
import json
from collections.abc import Callable
from typing import Any

import httpx
from api_helpers import admin
from fastapi.testclient import TestClient

SYNC = "/api/v1/catalog/sync"
BAMBU = "bambu-uuid-0000-0000-000000000001"
OTHER = "other-uuid-0000-0000-000000000002"
ETAG = '"v1-etag"'
LAST_MODIFIED = "Sat, 14 Nov 2026 02:23:50 GMT"


def _brand(uuid: str, name: str, slug: str, **extra: Any) -> dict[str, Any]:
    return {"uuid": uuid, "id": f"id-{uuid}", "name": name, "slug": slug, **extra}


def export(version: str = "2026.11.14") -> dict[str, Any]:
    """Bambu Lab with two filament lines (PLA Basic with Black, Jade White and a two-color
    gradient; PETG HF with a discontinued Cream), and another brand that must be dropped."""
    return {
        "version": version,
        "generated_at": "2026-11-14T02:22:51Z",
        "brands": [
            _brand(OTHER, "Other Brand", "other_brand"),
            _brand(BAMBU, "Bambu Lab", "bambu_lab", moved_from=["old-bambu-uuid"]),
        ],
        "filaments": [
            {
                "uuid": "fil-pla-basic",
                "id": "id-fil-pla-basic",
                "name": "PLA Basic",
                "material": "PLA",
                "brand_id": f"id-{BAMBU}",
                "density": 1.26,
                "min_print_temperature": 190,
                "max_print_temperature": 230,
                "min_bed_temperature": 35,
                "max_bed_temperature": 45,
                "discontinued": False,
            },
            {
                "uuid": "fil-petg-hf",
                "id": "id-fil-petg-hf",
                "name": "PETG HF",
                "material": "PETG",
                "brand_id": f"id-{BAMBU}",
                "density": 1.25,
                "discontinued": False,
                "moved_from": ["old-petg-uuid"],
            },
            {
                "uuid": "fil-other-pla",
                "id": "id-fil-other-pla",
                "name": "Other PLA",
                "material": "PLA",
                "brand_id": f"id-{OTHER}",
                "density": 1.24,
                "discontinued": False,
            },
        ],
        "variants": [
            _variant("var-black", "Black", "#000000", "id-fil-pla-basic"),
            _variant("var-jade", "Jade White", "#ffffff", "id-fil-pla-basic"),
            _variant(
                "var-gradient",
                "Arctic Whisper",
                "#9CDBD9",
                "id-fil-pla-basic",
                color_hexes=["#9CDBD9", "#FFFFFF"],
            ),
            _variant(
                "var-cream",
                "Cream",
                "#F3E0B8",
                "id-fil-petg-hf",
                discontinued=True,
                moved_from=["x"],
            ),
            _variant("var-other", "Other Red", "#FF0000", "id-fil-other-pla"),
        ],
        "sizes": [
            {
                "uuid": "size-black-refill",
                "id": "id-size-black-refill",
                "variant_id": "id-var-black",
                "filament_weight": 1000,
                "spool_refill": True,
                "article_number": "10101",
                "discontinued": False,
            },
            {
                "uuid": "size-black-spool",
                "id": "id-size-black-spool",
                "variant_id": "id-var-black",
                "filament_weight": 1000,
                "discontinued": False,
            },
            {
                "uuid": "size-other",
                "id": "id-size-other",
                "variant_id": "id-var-other",
                "filament_weight": 750,
                "discontinued": False,
            },
        ],
        "stores": [{"uuid": "store-uuid", "id": "id-store", "name": "Bambu Lab US"}],
        "purchase_links": [
            {
                "id": "link-1",
                "store_id": "id-store",
                "size_id": "id-size-black-refill",
                "url": "https://store.example/black-refill",
                "spool_refill": True,
            },
            {
                "id": "link-2",
                "store_id": "id-store",
                "size_id": "id-size-other",
                "url": "https://store.example/other",
                "spool_refill": False,
            },
        ],
    }


def _variant(uuid: str, name: str, hex_: str, filament_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "uuid": uuid,
        "id": f"id-{uuid}",
        "name": name,
        "color_hex": hex_,
        "filament_id": filament_id,
        "discontinued": False,
        **extra,
    }


def changed_export() -> dict[str, Any]:
    """The next day's export: Jade White is gone and PLA Basic gains Red."""
    data = export("2026.11.15")
    data["variants"] = [v for v in data["variants"] if v["uuid"] != "var-jade"]
    data["variants"].append(_variant("var-red", "Red", "#C12E1F", "id-fil-pla-basic"))
    return data


def gz(data: Any) -> bytes:
    return gzip.compress(json.dumps(data).encode())


Handler = Callable[[httpx.Request], httpx.Response]


def ok(body: bytes, etag: str = ETAG, last_modified: str = LAST_MODIFIED) -> Handler:
    headers = {"ETag": etag, "Last-Modified": last_modified}
    return lambda _: httpx.Response(200, content=body, headers=headers)


def status(code: int) -> Handler:
    return lambda _: httpx.Response(code)


Answer = Exception | Handler


class FakeOfdb:
    """Serves the queued answers in order (the last one repeats) and keeps every request."""

    def __init__(self, *answers: Answer) -> None:
        self.answers: list[Answer] = list(answers) or [ok(gz(export()))]
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def serve(self, *answers: Answer) -> None:
        self.answers = list(answers)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer(request)


def refresh(client: TestClient) -> dict[str, Any]:
    """Refresh now, as an Admin; the new sync status."""
    response = client.post(SYNC, headers=admin())
    assert response.status_code == 200, response.text
    return response.json()
