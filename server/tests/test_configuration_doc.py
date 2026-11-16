"""docs/configuration.md lists exactly the settings the server reads, and marks exactly the
ones the app can set."""

import re
from pathlib import Path

from filament_tracker.app_settings.registry import DEFINITIONS
from filament_tracker.config import Settings

DOC = Path(__file__).parents[2] / "docs" / "configuration.md"


def _rows() -> dict[str, str]:
    """Each setting named in the table, with its "In the app" cell."""
    rows: dict[str, str] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        for name in re.findall(r"`([A-Z][A-Z0-9_]*)`", cells[0]):
            rows[name] = cells[-1]
    return rows


def test_the_table_lists_every_setting_the_server_reads_and_no_others() -> None:
    read = {name.upper() for name in Settings.model_fields}

    assert set(_rows()) == read


def test_the_table_marks_the_settings_the_app_can_set() -> None:
    # The Settings page edits the registry's settings; the Devices page edits printers.
    in_app = {d.env.upper() for d in DEFINITIONS} | {"PRINTERS"}

    marked = {name for name, cell in _rows().items() if cell.lower().startswith("yes")}

    assert marked == in_app
