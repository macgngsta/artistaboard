"""Engine/session management. SQLite-first (a one-DSN swap to Postgres for deploy).

The engine is a module global initialised from ``settings.database_url`` when the
app starts (``init_engine``), so request handlers and the (later) board worker share
one connection pool. Tables are created on startup via ``create_db_and_tables``;
Alembic migrations arrive when the schema stabilises (Phase 2).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401 — register tables on SQLModel.metadata

_engine: Engine | None = None


def init_engine(database_url: str) -> Engine:
    global _engine
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, connect_args=connect_args)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("database engine not initialised; call init_engine() first")
    return _engine


def create_db_and_tables(engine: Engine | None = None) -> None:
    SQLModel.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency: a request-scoped session."""
    with Session(get_engine()) as session:
        yield session
