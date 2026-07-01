"""SQLModel tables for the web app.

``User`` and ``Scene`` back the design surface; ``Board``, ``Pipeline`` /
``PipelineEntry`` and ``BoardRun`` back the runtime (a pipeline running on a board).
Every owned row carries ``owner_id`` so queries scope to the current user;
``Scene.is_system`` rows are shared, read-only seed templates (``owner_id`` null).
``BoardRun`` holds the live rotation/last-sent state so a run survives a restart.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, Index
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


class Board(SQLModel, table=True):
    __tablename__ = "boards"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_id: str = Field(foreign_key="users.id", index=True)
    name: str
    model: str = "flagship"
    rows: int = 6
    cols: int = 22
    # Vestaboard Read/Write key, encrypted at rest (crypto.encrypt); last4 for display.
    rw_key_encrypted: str = ""
    rw_key_last4: str = ""
    min_send_interval: int = 15  # seconds; the board drops faster sends
    status: str = "unconfigured"  # unconfigured / ok / unreachable
    last_painted_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)


class Pipeline(SQLModel, table=True):
    __tablename__ = "pipelines"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_id: str = Field(foreign_key="users.id", index=True)
    name: str
    loop: bool = True
    created_at: datetime = Field(default_factory=_now)


class PipelineEntry(SQLModel, table=True):
    __tablename__ = "pipeline_entries"

    id: str = Field(default_factory=_uuid, primary_key=True)
    pipeline_id: str = Field(foreign_key="pipelines.id", index=True)
    position: int = 0
    duration_seconds: int = 60  # how long this entry holds the board
    refresh_seconds: int | None = None  # re-render cadence within the window (live data)
    # An entry renders either a built-in job (job_name) or a stored scene (scene_id).
    source_type: str = "job"  # job / scene
    job_name: str | None = None
    scene_id: str | None = Field(default=None, foreign_key="scenes.id")
    # For scene entries: a job whose bind() envelope feeds the scene's variables
    # (auto-bound by name). None -> the scene renders static (fallbacks only).
    data_source: str | None = None
    # Typed per-entry job options (validated against the driving job's Options schema
    # on write), applied as Settings overrides when the entry renders. {} -> inherit
    # the process-global defaults. The driving job is job_name, or data_source for a scene.
    options: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class BoardRun(SQLModel, table=True):
    __tablename__ = "board_runs"

    # One run row per board (the board is the unit a worker owns).
    board_id: str = Field(foreign_key="boards.id", primary_key=True)
    owner_id: str = Field(foreign_key="users.id", index=True)
    pipeline_id: str = Field(foreign_key="pipelines.id")
    state: str = "stopped"  # running / paused / stopped
    rotation_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    last_sent: list[list[int]] | None = Field(default=None, sa_column=Column(JSON))
    current_entry_id: str | None = None
    updated_at: datetime = Field(default_factory=_now)


class DataSnapshot(SQLModel, table=True):
    """A reading from a data source, persisted by the poller so the paint path reads
    the DB instead of calling an API. Append-only time series: one row per poll.

    ``payload`` holds the source's full normalized data (not a single scene's
    envelope), so a board can re-filter or switch what it shows without re-fetching.
    ``source_key`` is the fetch-defining identity (e.g. a Muni stop / sport league);
    display-only options (a group filter, which lines) are applied at render, not here.

    On Postgres this table is RANGE-partitioned by ``fetched_at`` (monthly, with
    DROP-partition retention — see db.partitions); on SQLite it's a plain table. The
    ORM read/write path is identical on both.
    """

    __tablename__ = "data_snapshots"
    __table_args__ = (Index("ix_data_snapshots_latest", "source", "source_key", "fetched_at"),)

    id: int | None = Field(default=None, primary_key=True)
    source: str  # job/source name, e.g. "world_cup"
    source_key: str = ""  # fetch-defining options identity ("" = the source's default)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=_now)
