"""SQLModel tables for the web app.

Phase 1 introduces the two tables the vertical slice needs — ``User`` and
``Scene``. The other entities (Board, Pipeline, …) land with the pipeline runner.
Every owned row carries ``owner_id`` so queries scope to the current user;
``Scene.is_system`` rows are shared, read-only seed templates (``owner_id`` null).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_uuid, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    display_name: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=_now)


class Scene(SQLModel, table=True):
    __tablename__ = "scenes"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_id: str | None = Field(default=None, foreign_key="users.id", index=True)
    name: str
    description: str = ""
    model: str = "flagship"  # flagship 6x22 / note 15x3
    rows: int = 6
    cols: int = 22
    is_system: bool = False
    # The object-form scene JSON, stored verbatim (loads via Scene.from_dict).
    document: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # Derived: the envelope variables the document needs (render.scene_variables).
    required_variables: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
