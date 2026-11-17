"""Read BambuStudio's color code list (`filaments_color_codes.json`) into rows.

The list is `{"data": [...]}`, one entry per color Bambu Lab sells: its Bambu code
(`fila_color_code`), the filament ID its tags read as material ID (`fila_id`, such as GFA00)
and BambuStudio's color code (`color_code`, such as K0). Only those three are kept.

Anything wrong (bad JSON, a changed shape, a missing or malformed field, no entries) raises
ListInvalid with a short reason, so the sync can keep the last good copy.
"""

import json
from typing import Annotated, Any

from pydantic import BaseModel, Field, ValidationError

Code = Annotated[str, Field(min_length=1, max_length=16, pattern=r"^[0-9]+$")]
Id = Annotated[str, Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9]+$")]


class ListInvalid(ValueError):
    """The list can't be used. The message is a short reason, safe to show an Admin."""


class _Entry(BaseModel):
    fila_color_code: Code
    fila_id: Id
    color_code: Id


def parse_color_codes(raw: bytes) -> list[dict[str, Any]]:
    """Rows for the bambu_color_code table, in the list's order."""
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ListInvalid("the file is not valid JSON") from None
    entries = data.get("data") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ListInvalid("the file's format changed")
    if not entries:
        raise ListInvalid("the file has no entries")
    return [_row(entry) for entry in entries]


def _row(entry: dict[str, Any]) -> dict[str, Any]:
    try:
        checked = _Entry.model_validate(entry)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"])
        if first["type"] == "missing":
            raise ListInvalid(f"the file has a missing field: {field}") from None
        raise ListInvalid(f"the file has a field that is not valid: {field}") from None
    return {
        "bambu_code": checked.fila_color_code,
        "filament_id": checked.fila_id,
        "color_code": checked.color_code,
    }
