"""docs/configuration.md lists exactly the settings the server reads, and marks exactly the
ones the app can set."""

import re
from pathlib import Path

from filament_tracker.app_settings.registry import DEFINITIONS
from filament_tracker.config import Settings

DOC = Path(__file__).parents[2] / "docs" / "configuration.md"


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _rows(text: str | None = None) -> dict[str, str]:
    """Each setting named in the table, with its "In the app" cell, finding both columns by
    their header."""
    if text is None:
        text = DOC.read_text(encoding="utf-8")
    rows: dict[str, str] = {}
    header: list[str] | None = None
    for line in text.splitlines():
        if not line.startswith("|"):
            header = None  # the table has ended
            continue
        cells = _cells(line)
        if {"Setting", "In the app"} <= set(cells):
            header = cells
            continue
        if header is None or set(line) <= set("|- "):
            continue
        name_cell = cells[header.index("Setting")]
        for name in re.findall(r"`([A-Z][A-Z0-9_]*)`", name_cell):
            rows[name] = cells[header.index("In the app")]
    return rows


def test_the_table_lists_every_setting_the_server_reads_and_no_others() -> None:
    read = {name.upper() for name in Settings.model_fields}

    assert set(_rows()) == read


def test_the_table_marks_the_settings_the_app_can_set() -> None:
    # The Settings page edits the registry's settings; the Devices page edits printers.
    in_app = {d.env.upper() for d in DEFINITIONS} | {"PRINTERS"}

    marked = {name for name, cell in _rows().items() if cell.lower().startswith("yes")}

    assert marked == in_app


def test_the_columns_are_found_by_their_headers_not_their_order() -> None:
    table = "\n".join(
        [
            "| In the app | Purpose | Setting |",
            "| --- | --- | --- |",
            "| Yes | Where scans go | `TZ` |",
            "| No | Who may connect | `TRUSTED_NETWORKS` |",
        ]
    )

    assert _rows(table) == {"TZ": "Yes", "TRUSTED_NETWORKS": "No"}
