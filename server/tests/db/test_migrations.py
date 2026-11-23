from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.util import CommandError
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from filament_tracker.db.engine import create_db_engine
from filament_tracker.db.migrate import downgrade, upgrade
from filament_tracker.db.models import Base

TABLES = {"product", "spool", "spool_hold", "tag", "event", "device", "printer", "user", "session"}


def test_upgrade_creates_every_table(engine: Engine) -> None:
    assert TABLES <= set(inspect(engine).get_table_names())


def test_migrations_match_the_models(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []


def test_upgrade_is_safe_to_run_twice(engine: Engine, db_url: str) -> None:
    upgrade(db_url)

    assert TABLES <= set(inspect(engine).get_table_names())


def test_upgrade_leaves_a_current_database_as_it_is(engine: Engine, db_url: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user (id, username, password_hash, role, password_changed_at,"
                " created_at) VALUES (1, 'frank', 'x', 'admin', :w, :w)"
            ),
            {"w": "2026-11-21 12:00:00.000000"},
        )

    def revision_schema_and_rows() -> tuple[object, ...]:
        with engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
            schema = connection.execute(
                text("SELECT type, name, sql FROM sqlite_master ORDER BY name")
            ).all()
            users = connection.execute(text("SELECT id, username FROM user")).all()
        return revision, schema, users

    before = revision_schema_and_rows()
    revision, _, _ = before
    assert revision is not None

    upgrade(db_url)

    assert revision_schema_and_rows() == before


def test_upgrade_refuses_a_database_at_an_unknown_revision(engine: Engine, db_url: str) -> None:
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'notarevision'"))

    with pytest.raises(CommandError):
        upgrade(db_url)


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


def test_the_request_pipeline_keeps_existing_requests_submitted(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'requests.db'}"
    upgrade(url, "8be4824dafad")
    engine = create_db_engine(url)
    when = "2026-11-18 12:00:00.000000"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user (id, username, password_hash, role, requester,"
                " password_changed_at, created_at) VALUES (1, 'sam', 'x', 'viewer', 1, :w, :w)"
            ),
            {"w": when},
        )
        connection.execute(
            text(
                "INSERT INTO print_request (id, requester_id, title, notes, quantity, priority,"
                " status, created_at, updated_at) VALUES (1, 1, 'Lamp', 'here', 1, 'normal',"
                " 'submitted', :w, :w)"
            ),
            {"w": when},
        )
        connection.execute(
            text(
                "INSERT INTO request_history (request_id, kind, user_id, at)"
                " VALUES (1, 'submitted', 1, :w)"
            ),
            {"w": when},
        )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.begin() as connection:
        status = connection.execute(text("SELECT status FROM print_request")).scalar()
        kinds = connection.execute(text("SELECT kind FROM request_history")).scalars().all()
        # The widened checks take the new statuses and history kind, and nothing else.
        connection.execute(text("UPDATE print_request SET status = 'waiting_on_filament'"))
        connection.execute(
            text(
                "INSERT INTO request_history (request_id, kind, user_id, at)"
                " VALUES (1, 'status_changed', 1, :w)"
            ),
            {"w": when},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE print_request SET status = 'lost'"))
    engine.dispose()
    assert (status, kinds) == ("submitted", ["submitted"])

    downgrade(url, "8be4824dafad")

    engine = create_db_engine(url)
    with engine.connect() as connection:
        status = connection.execute(text("SELECT status FROM print_request")).scalar()
        kinds = connection.execute(text("SELECT kind FROM request_history")).scalars().all()
    engine.dispose()
    assert (status, kinds) == ("submitted", ["submitted"])


def test_existing_spools_get_net_weight_and_grams_left(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'spools.db'}"
    upgrade(url, "29efdaa213bf")
    engine = create_db_engine(url)
    when = "2026-11-20 12:00:00.000000"
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO catalog_brand VALUES ('b', 'Bambu Lab', '[]')"))
        connection.execute(
            text(
                "INSERT INTO catalog_filament (uuid, brand_uuid, position, name, material,"
                " moved_from) VALUES ('f', 'b', 0, 'TPU', 'TPU', '[]')"
            )
        )
        for color in ("one", "two", "same"):
            connection.execute(
                text(
                    "INSERT INTO catalog_variant (uuid, filament_uuid, position, name, color_hex,"
                    " extra_hexes, gradient, discontinued, moved_from)"
                    " VALUES (:c, 'f', 0, :c, 'FF0000', '[]', 0, 0, '[]')"
                ),
                {"c": color},
            )
        for size, color, weight in [
            ("s1", "one", 500.0),
            ("s2", "two", 500.0),
            ("s3", "two", 250),
            ("s4", "same", 750.0),
            ("s5", "same", 750.0),
        ]:
            connection.execute(
                text(
                    "INSERT INTO catalog_size (uuid, variant_uuid, filament_weight, refill,"
                    " discontinued, purchase_links, moved_from)"
                    " VALUES (:s, :c, :w, 0, 0, '[]', '[]')"
                ),
                {"s": size, "c": color, "w": weight},
            )
        # 1: no catalog link; 2: linked by hand to a color with one size; 3: linked by its
        # tag to a color with two weights; 4: to a color with two sizes of one weight.
        for id_, manual, auto in [
            (1, None, None),
            (2, "one", None),
            (3, None, "two"),
            (4, None, "same"),
        ]:
            connection.execute(
                text(
                    "INSERT INTO product (id, filament_type, color_rgba, display_name,"
                    " low_stock_threshold, provisional, created_at, catalog_manual_uuid,"
                    " catalog_auto_uuid) VALUES (:id, 'TPU', 'FF0000FF', 'TPU', 0, 0, :w, :m, :a)"
                ),
                {"id": id_, "w": when, "m": manual, "a": auto},
            )
        spools = [
            # id, product, state, remaining %, tag weight
            (1, 1, "sealed", None, 750),  # sealed, from its tag
            (2, 1, "open", 40, 750),  # open with a remaining %
            (3, 1, "open", None, 750),  # open, no remaining %: unknown
            (4, 2, "sealed", None, None),  # placeholder, its color's only size
            (5, 3, "sealed", None, None),  # placeholder, a color with two sizes
            (6, 1, "open", 50, None),  # seen by the AMS first, no tag
            (7, 1, "empty", 0, 1000),  # empty: unknown
            (8, 1, None, None, 0),  # Unknown state, a tag with no weight
            (9, 4, "sealed", None, None),  # placeholder, two sizes of one weight
        ]
        for id_, product, state, pct, weight in spools:
            connection.execute(
                text(
                    "INSERT INTO spool (id, product_id, state, remaining_pct, created_at)"
                    " VALUES (:id, :p, :s, :pct, :w)"
                ),
                {"id": id_, "p": product, "s": state, "pct": pct, "w": when},
            )
            if weight is not None:
                connection.execute(
                    text(
                        "INSERT INTO tag (uid, spool_id, decoded_json, first_seen_at)"
                        " VALUES (:uid, :id, :json, :w)"
                    ),
                    {
                        "uid": f"{id_:08X}",
                        "id": id_,
                        "json": f'{{"spool_weight_g": {weight}}}',
                        "w": when,
                    },
                )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, net_weight_g, grams_left_g FROM spool ORDER BY id")
        ).all()
    engine.dispose()
    assert [tuple(row) for row in rows] == [
        (1, 750, 750),
        (2, 750, 300),
        (3, 750, None),
        (4, 500, 500),
        (5, 1000, 1000),
        (6, 1000, 500),
        (7, 1000, None),
        (8, 1000, None),
        (9, 750, 750),
    ]


def test_spools_already_here_count_as_arrived_and_new_ones_do_not(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'arrivals.db'}"
    upgrade(url, "9d41c6b7e2a3")
    engine = create_db_engine(url)
    when = "2026-11-21 12:00:00.000000"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO product (id, filament_type, color_rgba, display_name,"
                " low_stock_threshold, provisional, created_at) VALUES (1, 'PLA', '000000FF',"
                " 'Black', 0, 0, :when)"
            ),
            {"when": when},
        )
        connection.execute(
            text("INSERT INTO spool (id, product_id, created_at) VALUES (1, 1, :when)"),
            {"when": when},
        )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO spool (id, product_id, created_at) VALUES (2, 1, :when)"),
            {"when": when},
        )
        counted = connection.execute(
            text("SELECT id, arrival_counted FROM spool ORDER BY id")
        ).all()
        products = connection.execute(text("SELECT from_catalog FROM product")).all()
    engine.dispose()
    assert [tuple(row) for row in counted] == [(1, 1), (2, 0)]
    assert [tuple(row) for row in products] == [(0,)]


def test_the_email_switches_carry_over_as_notification_choices(tmp_path: Path) -> None:
    # Only a switch that was off is stored; one that was on matches the default.
    url = f"sqlite:///{tmp_path / 'switches.db'}"
    upgrade(url, "f643878a99ce")
    engine = create_db_engine(url)
    when = "2026-11-22 12:00:00.000000"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user (id, username, password_hash, role, password_changed_at,"
                " created_at, email_on_request_change, email_on_new_request) VALUES"
                " (1, 'both_on', 'x', 'admin', :w, :w, 1, 1),"
                " (2, 'changes_off', 'x', 'admin', :w, :w, 0, 1),"
                " (3, 'new_off', 'x', 'admin', :w, :w, 1, 0),"
                " (4, 'both_off', 'x', 'viewer', :w, :w, 0, 0)"
            ),
            {"w": when},
        )
        connection.execute(
            text(
                "INSERT INTO session (token_hash, user_id, created_at, expires_at, last_seen_at)"
                " VALUES (:t, 4, :w, :w, :w)"
            ),
            {"t": "a" * 64, "w": when},
        )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        choices = connection.execute(
            text('SELECT user_id, kind, channel, "on" FROM notification_choice ORDER BY 1, 2')
        ).all()
        sessions = connection.execute(text("SELECT count(*) FROM session")).scalar()
    columns = [c["name"] for c in inspect(engine).get_columns("user")]
    engine.dispose()
    assert [tuple(row) for row in choices] == [
        (2, "new_photo", "email", 0),
        (2, "request_update", "email", 0),
        (3, "new_request", "email", 0),
        (4, "new_photo", "email", 0),
        (4, "new_request", "email", 0),
        (4, "request_update", "email", 0),
    ]
    assert sessions == 1
    assert not [c for c in columns if c.startswith("email_on_")]

    downgrade(url, "f643878a99ce")

    engine = create_db_engine(url)
    with engine.connect() as connection:
        switches = connection.execute(
            text(
                "SELECT username, email_on_request_change, email_on_new_request FROM user"
                " ORDER BY id"
            )
        ).all()
    tables = inspect(engine).get_table_names()
    engine.dispose()
    assert [tuple(row) for row in switches] == [
        ("both_on", 1, 1),
        ("changes_off", 0, 1),
        ("new_off", 1, 0),
        ("both_off", 0, 0),
    ]
    assert "notification_choice" not in tables
