"""`ft-admin restore --for-test`: a test server's copy of the newest live backup, scrubbed so
it can't reach the household."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from filament_tracker.admin_cli import main
from filament_tracker.config import Settings


NOW = "2026-11-20 08:00:00.000000"


def _db(path: Path, template: Path) -> Path:
    """A migrated database at path, copied from the session's template."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, path)
    return path


def _run(path: Path, sql: str, *params: object) -> None:
    with sqlite3.connect(path) as db:
        db.execute(sql, params)
    db.close()


def _rows(path: Path, sql: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as db:
        rows = db.execute(sql).fetchall()
    db.close()
    return rows


def _add_user(path: Path, username: str) -> None:
    _run(
        path,
        "INSERT INTO user (username, password_hash, role, password_changed_at, created_at)"
        " VALUES (?, 'hash', 'admin', ?, ?)",
        username,
        NOW,
        NOW,
    )


def _usernames(path: Path) -> list[str]:
    return [name for (name,) in _rows(path, "SELECT username FROM user ORDER BY username")]


@pytest.fixture
def backups(tmp_path: Path) -> Path:
    folder = tmp_path / "backups"
    folder.mkdir()
    return folder


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return tmp_path / "data" / "filament.db"


@pytest.fixture
def settings(target: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{target}", _env_file=None)


def test_refuses_when_the_backups_directory_has_no_backup(
    backups: Path, target: Path, settings: Settings, capsys
) -> None:
    (backups / "notes.txt").write_text("not a backup", encoding="utf-8")

    code = main(["restore", "--for-test", str(backups)], settings=settings)

    assert code == 1
    assert f"no backup in {backups}" in capsys.readouterr().err
    assert not target.exists()


def test_restores_the_newest_of_several_backups_over_the_database(
    backups: Path, target: Path, settings: Settings, migrated_template: Path, capsys
) -> None:
    for name in (
        "filament-20261118T080000Z.db",
        "filament-20261120T080000Z.db",
        "filament-20261119T080000Z.db",
    ):
        _add_user(_db(backups / name, migrated_template), name[9:17])
    _add_user(_db(target, migrated_template), "replaced")

    code = main(["restore", "--for-test", str(backups)], settings=settings)

    assert code == 0
    assert _usernames(target) == ["20261120"]
    assert "restored filament-20261120T080000Z.db" in capsys.readouterr().out
    assert len(list(backups.iterdir())) == 3
