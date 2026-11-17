"""A fake BambuStudio color code list for catalog tests. Hand-written in the shape of
BambuStudio's `filaments_color_codes.json`, not an excerpt of it (that file is AGPL-3.0).

The entries pair with `ofdb_fake.export()`, where PLA Basic Black's sizes carry Bambu code
10101: a tag reading material ID GFA00 and variant ID A00-K0 links to it.
"""

import json
from typing import Any

BAMBUSTUDIO_URL = (
    "https://raw.githubusercontent.com/bambulab/BambuStudio/master/resources/profiles/BBL/"
    "filament/filaments_color_codes.json"
)
BAMBUSTUDIO_ETAG = '"bs-v1"'


def entry(code: str, filament_id: str, color_code: str, name: str = "Black") -> dict[str, Any]:
    return {
        "fila_color_code": code,
        "fila_id": filament_id,
        "fila_color_type": "single",
        "fila_type": "PLA Basic",
        "fila_color_name": {"en": name, "de": name},
        "color_code": color_code,
        "fila_color": ["#000000FF"],
    }


def color_codes(*entries: dict[str, Any]) -> dict[str, Any]:
    """The list: by default PLA Basic Black (10101, GFA00, K0) and a code OFDB lacks."""
    data = list(entries) or [entry("10101", "GFA00", "K0"), entry("99999", "GFA00", "Z9", "Gone")]
    return {"data": data, "total": len(data)}


def body(data: Any) -> bytes:
    return json.dumps(data).encode()
