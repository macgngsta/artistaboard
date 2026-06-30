"""Programmatic Alembic entry point used by the app at startup.

Resolves the migrations directory relative to the package (robust under any
install) and upgrades to ``head`` against the given database URL.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def run_migrations(database_url: str) -> None:
    command.upgrade(_config(database_url), "head")
