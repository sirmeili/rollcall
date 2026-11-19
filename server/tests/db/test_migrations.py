from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from filament_tracker.db.engine import create_db_engine
from filament_tracker.db.migrate import downgrade, upgrade
from filament_tracker.db.models import Base

TABLES = {"product", "spool", "tag", "event", "device", "printer", "user", "session"}


def test_upgrade_creates_every_table(engine: Engine) -> None:
    assert TABLES <= set(inspect(engine).get_table_names())


def test_migrations_match_the_models(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []


def test_upgrade_is_safe_to_run_twice(engine: Engine, db_url: str) -> None:
    upgrade(db_url)

    assert TABLES <= set(inspect(engine).get_table_names())


def test_downgrade_removes_every_table(db_url: str) -> None:
    upgrade(db_url)
    downgrade(db_url, "base")

    engine = create_db_engine(db_url)
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()


def test_upgrade_from_an_empty_database(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'empty.db'}"

    upgrade(url)

    engine = create_db_engine(url)
    assert TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def _catalog_variant_columns(url: str) -> list[str]:
    engine = create_db_engine(url)
    columns = [c["name"] for c in inspect(engine).get_columns("catalog_variant")]
    engine.dispose()
    return columns


def test_the_gradient_column_comes_and_goes_with_a_synced_catalog(tmp_path: Path) -> None:
    # A synced catalog has sizes referencing its colors, and foreign keys are on: a migration
    # that copies and drops catalog_variant fails on it.
    url = f"sqlite:///{tmp_path / 'synced.db'}"
    upgrade(url, "06a52b9751a5")
    engine = create_db_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO catalog_brand VALUES ('b', 'Bambu Lab', '[]')"),
        )
        connection.execute(
            text(
                "INSERT INTO catalog_filament (uuid, brand_uuid, position, name, material,"
                " moved_from) VALUES ('f', 'b', 0, 'PLA Basic Gradient', 'PLA', '[]')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO catalog_variant (uuid, filament_uuid, position, name, color_hex,"
                " extra_hexes, discontinued, moved_from)"
                " VALUES ('v', 'f', 0, 'Dusk Glare', 'ED9558', '[\"CE4406\"]', 0, '[]')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO catalog_size (uuid, variant_uuid, filament_weight, refill,"
                " discontinued, purchase_links, moved_from) VALUES ('s', 'v', 1000, 0, 0, '[]',"
                " '[]')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO catalog_sync (started_at, finished_at, result, dataset_version, etag,"
                " last_modified) VALUES ('2026-11-16 04:00:00.000000',"
                " '2026-11-16 04:00:05.000000', 'updated', '2026.11.15', '\"abc\"',"
                " 'Sun, 15 Nov 2026 02:22:51 GMT')"
            )
        )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT uuid, gradient FROM catalog_variant")).all()
        sizes = connection.execute(text("SELECT count(*) FROM catalog_size")).scalar()
        sync = connection.execute(
            text("SELECT dataset_version, etag, last_modified FROM catalog_sync")
        ).all()
    engine.dispose()
    # Not known until the next sync fills it in.
    assert [tuple(row) for row in rows] == [("v", 0)]
    assert sizes == 1
    # So that sync downloads the export in full, even when OFDB has nothing new.
    assert [tuple(row) for row in sync] == [("2026.11.15", None, None)]

    downgrade(url, "06a52b9751a5")

    assert "gradient" not in _catalog_variant_columns(url)


def test_products_already_made_from_the_ams_are_marked(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade(url, "92998d06ecab")
    engine = create_db_engine(url)
    when = "2026-11-10 12:00:00.000000"
    product = (
        "INSERT INTO product (id, filament_type, color_rgba, display_name,"
        " low_stock_threshold, provisional, created_at) VALUES (:id, 'PETG', '000000FF', :name,"
        " 0, :provisional, :when)"
    )
    spool = (
        "INSERT INTO spool (id, product_id, tray_uid, created_at) VALUES (:id, :p, :tray, :when)"
    )
    event = (
        "INSERT INTO event (id, spool_id, type, source, occurred_at, recorded_at, flagged)"
        " VALUES (:id, :spool, 'opened', :source, :when, :when, 0)"
    )
    with engine.begin() as connection:
        # 1: made by the AMS; 2: by hand, a placeholder opened in the web app;
        # 3: from a tag, later seen by the AMS.
        for id_, name, provisional in [(1, "PETG HF Black", 1), (2, "Hand", 1), (3, "Tag", 0)]:
            connection.execute(
                text(product), {"id": id_, "name": name, "provisional": provisional, "when": when}
            )
        for id_, tray in [(1, "A" * 32), (2, None), (3, "B" * 32)]:
            connection.execute(text(spool), {"id": id_, "p": id_, "tray": tray, "when": when})
        for id_, spool_id, source in [(1, 1, "ams"), (2, 2, "ui"), (3, 3, "ams")]:
            connection.execute(
                text(event),
                {"id": f"{id_:032x}", "spool": spool_id, "source": source, "when": when},
            )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        marked = connection.execute(text("SELECT id, from_ams FROM product ORDER BY id")).all()
    engine.dispose()
    assert [tuple(row) for row in marked] == [(1, 1), (2, 0), (3, 0)]


def test_catalog_links_upgrade_a_synced_catalog_with_products(tmp_path: Path) -> None:
    # Products have spools pointing at them and the catalog has synced: a migration that
    # copies and drops product fails on it.
    url = f"sqlite:///{tmp_path / 'synced.db'}"
    upgrade(url, "d02002b943bd")
    engine = create_db_engine(url)
    when = "2026-11-16 12:00:00.000000"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO product (id, material_id, variant_id, filament_type, color_rgba,"
                " display_name, low_stock_threshold, nearly_out_pct, provisional, from_ams,"
                " created_at) VALUES (1, 'GFA00', 'A00-K0', 'PLA', '000000FF', 'PLA Basic Black',"
                " 0, 15, 0, 0, :when)"
            ),
            {"when": when},
        )
        connection.execute(
            text("INSERT INTO spool (id, product_id, tray_uid, created_at) VALUES (1, 1, :t, :w)"),
            {"t": "A" * 32, "w": when},
        )
        connection.execute(
            text(
                "INSERT INTO catalog_sync (started_at, finished_at, result, dataset_version)"
                " VALUES (:w, :w, 'updated', '2026.11.15')"
            ),
            {"w": when},
        )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        sync = connection.execute(text("SELECT source, dataset_version FROM catalog_sync")).all()
        product = connection.execute(
            text(
                "SELECT display_name, catalog_auto_uuid, catalog_manual_uuid, catalog_manual_by"
                " FROM product"
            )
        ).all()
        spools = connection.execute(text("SELECT count(*) FROM spool")).scalar()
    engine.dispose()
    # The syncs so far were OFDB's; products are linked by the next sync.
    assert [tuple(row) for row in sync] == [("ofdb", "2026.11.15")]
    assert [tuple(row) for row in product] == [("PLA Basic Black", None, None, None)]
    assert spools == 1

    downgrade(url, "d02002b943bd")

    engine = create_db_engine(url)
    columns = [c["name"] for c in inspect(engine).get_columns("product")]
    tables = inspect(engine).get_table_names()
    engine.dispose()
    assert not [c for c in columns if c.startswith("catalog_")]
    assert "bambu_color_code" not in tables


def test_requester_upgrades_existing_users_left_off(tmp_path: Path) -> None:
    # Sessions point at the users: a migration that copies and drops user fails on it.
    url = f"sqlite:///{tmp_path / 'users.db'}"
    upgrade(url, "5b8e1c7d2a94")
    engine = create_db_engine(url)
    when = "2026-11-17 12:00:00.000000"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user (id, username, password_hash, role, password_changed_at,"
                " created_at) VALUES (1, 'frank', 'x', 'admin', :w, :w),"
                " (2, 'sam', 'x', 'viewer', :w, :w)"
            ),
            {"w": when},
        )
        connection.execute(
            text(
                "INSERT INTO session (token_hash, user_id, created_at, expires_at, last_seen_at)"
                " VALUES (:t, 2, :w, :w, :w)"
            ),
            {"t": "a" * 64, "w": when},
        )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        users = connection.execute(text("SELECT username, requester FROM user ORDER BY id")).all()
        sessions = connection.execute(text("SELECT count(*) FROM session")).scalar()
    engine.dispose()
    assert [tuple(row) for row in users] == [("frank", 0), ("sam", 0)]
    assert sessions == 1

    downgrade(url, "5b8e1c7d2a94")

    engine = create_db_engine(url)
    columns = [c["name"] for c in inspect(engine).get_columns("user")]
    tables = inspect(engine).get_table_names()
    engine.dispose()
    assert "requester" not in columns
    assert "print_request" not in tables
