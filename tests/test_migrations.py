"""Alembic upgrade/downgrade round-trip. Startup only ever runs ``upgrade head``
(db/migrate.py), so nothing else exercises the downgrade path or proves the
migrations are re-runnable — this does both against a throwaway SQLite DB."""

from alembic import command
from sqlalchemy import create_engine, inspect

from artistaboard.db.migrate import _config

# The tables the migrations own; alembic_version is bookkeeping and stays behind.
APP_TABLES = {
    "users",
    "scenes",
    "boards",
    "pipelines",
    "pipeline_entries",
    "board_runs",
    "data_snapshots",
}


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migrations_upgrade_downgrade_roundtrip(tmp_path):
    url = f"sqlite:///{tmp_path}/roundtrip.db"
    cfg = _config(url)

    command.upgrade(cfg, "head")
    assert APP_TABLES <= _tables(url)

    # Every migration's downgrade runs cleanly back to an empty schema.
    command.downgrade(cfg, "base")
    assert not (APP_TABLES & _tables(url))

    # ...and the full stack re-applies from a downgraded DB (no dangling state).
    command.upgrade(cfg, "head")
    assert APP_TABLES <= _tables(url)
