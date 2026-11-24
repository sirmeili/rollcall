"""ADR-0014: Print Requests depends on Inventory, never the reverse. Reads each Inventory
module's imports and fails on any import of Print Requests."""

import ast
from collections.abc import Iterable
from pathlib import Path

import filament_tracker

PACKAGE = Path(filament_tracker.__file__).parent
PRINT_REQUESTS = ("filament_tracker.print_requests", "filament_tracker.db.request_models")

# The request routes, which call Print Requests.
REQUEST_ROUTES = (
    "api/requests.py",
    "api/request_files.py",
    "api/request_holds.py",
    "api/request_photos.py",
    "api/request_schemas.py",
    "api/request_views.py",
)

# Print Requests' own code, its routes, and the app wiring, which sees both modules.
NOT_INVENTORY = ("print_requests/*", "db/request_models.py", *REQUEST_ROUTES, "main.py")

# Imports that were there before this test. models.py puts every table on Base, and auth
# answers /auth/me's has_requests. Each is allowed in that file only.
KNOWN = {
    "db/models.py": {"filament_tracker.db.request_models"},
    "api/auth.py": {"filament_tracker.print_requests.access"},
}


def _inventory_files() -> list[Path]:
    return [
        path
        for path in PACKAGE.rglob("*.py")
        if not any(path.relative_to(PACKAGE).match(pattern) for pattern in NOT_INVENTORY)
    ]


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _within(name: str, modules: Iterable[str]) -> bool:
    return any(name == m or name.startswith(f"{m}.") for m in modules)


def _print_requests(names: set[str]) -> set[str]:
    return {name for name in names if _within(name, PRINT_REQUESTS)}


def test_inventory_never_imports_print_requests() -> None:
    found = {}
    for path in _inventory_files():
        name = path.relative_to(PACKAGE).as_posix()
        known = KNOWN.get(name, set())
        imported = {i for i in _print_requests(_imports(path)) if not _within(i, known)}
        if imported:
            found[name] = sorted(imported)

    assert found == {}


def test_the_hold_service_and_its_table_are_checked() -> None:
    names = {path.relative_to(PACKAGE).as_posix() for path in _inventory_files()}

    assert {"services/holds.py", "db/models.py"} <= names


def test_the_shopping_list_is_checked() -> None:
    names = {path.relative_to(PACKAGE).as_posix() for path in _inventory_files()}

    assert {"services/shopping_list/read.py", "api/shopping_list.py"} <= names


def test_an_import_of_print_requests_is_found(tmp_path: Path) -> None:
    module = tmp_path / "leaky.py"
    module.write_text(
        "from filament_tracker.print_requests import pipeline\n"
        "import filament_tracker.db.request_models\n",
        encoding="utf-8",
    )

    assert _print_requests(_imports(module)) == {
        "filament_tracker.print_requests",
        "filament_tracker.print_requests.pipeline",
        "filament_tracker.db.request_models",
    }
