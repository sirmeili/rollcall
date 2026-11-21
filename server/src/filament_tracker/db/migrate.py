"""Run Alembic migrations from code; the server upgrades its database on startup.

An upgrade to the latest revision first reads the database's recorded revision and returns
at once when it is already the latest, so a start with nothing to migrate skips Alembic's
upgrade command (which loads every migration script). Any other case goes to Alembic.
"""

from functools import cache

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from filament_tracker.db.engine import create_db_engine

# The migrations live inside the package, so they ship with the installed server and the
# Docker image.
SCRIPT_LOCATION = "filament_tracker:migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    if revision == "head" and _current_heads(database_url) == _latest_heads():
        return
    command.upgrade(alembic_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    command.downgrade(alembic_config(database_url), revision)


@cache
def _latest_heads() -> frozenset[str]:
    """The migration scripts' latest revisions; they ship in the package, so they can't
    change while the process runs."""
    return frozenset(ScriptDirectory.from_config(alembic_config("")).get_heads())


def _current_heads(database_url: str) -> frozenset[str]:
    """The revisions recorded in the database; reading them creates nothing."""
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            return frozenset(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()
