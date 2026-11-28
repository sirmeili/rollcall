"""A test server's database: the newest live backup, scrubbed so it can't reach the
household (`ft-admin restore --for-test`).

It never migrates: a backup from an older release keeps its schema, so that release's image
starts on it, and the candidate's migrations run at the upgrade.
"""

import shutil
from pathlib import Path

from filament_tracker.app_settings.offline import database_file
from filament_tracker.services.backup import backups

# SQLite's files beside a database: a stale one would be replayed into the restored copy.
SIDE_FILES = ("-wal", "-shm", "-journal")


class NoBackup(Exception):
    """The backups directory holds no backup, or the database is not a file."""


def restore_for_test(backups_dir: Path, database_url: str) -> str:
    """Restore and scrub; returns what was restored and removed, for printing."""
    found = backups(backups_dir)
    if not found:
        raise NoBackup(f"no backup in {backups_dir}")
    target = database_file(database_url)
    if target is None:
        raise NoBackup("DATABASE_URL must be a SQLite file")
    newest = found[-1]
    _copy(newest, target)
    return f"restored {newest.name}"


def _copy(source: Path, target: Path) -> None:
    """Replace the database at target with a byte copy of source. The backups stay read
    only: a byte copy opens nothing in their directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in SIDE_FILES:
        target.with_name(target.name + suffix).unlink(missing_ok=True)
    partial = target.with_name(target.name + ".partial")
    shutil.copyfile(source, partial)
    partial.replace(target)
