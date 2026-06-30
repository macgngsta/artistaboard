"""Request/response models for the API (kept separate from the DB tables)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from ..db.models import Board, Scene


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str


class SceneIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    model: str = "flagship"
    document: dict[str, Any] | list[Any]


class SceneOut(BaseModel):
    id: str
    owner_id: str | None
    name: str
    description: str
    model: str
    rows: int
    cols: int
    is_system: bool
    document: Any
    required_variables: list[dict[str, Any]]

    @classmethod
    def of(cls, scene: Scene) -> SceneOut:
        return cls(
            id=scene.id,
            owner_id=scene.owner_id,
            name=scene.name,
            description=scene.description,
            model=scene.model,
            rows=scene.rows,
            cols=scene.cols,
            is_system=scene.is_system,
            document=scene.document,
            required_variables=scene.required_variables,
        )


class PreviewIn(BaseModel):
    document: dict[str, Any] | list[Any]
    sample_data: dict[str, Any] = Field(default_factory=dict)


class PreviewOut(BaseModel):
    rows: int
    cols: int
    characters: list[list[int]]


class BoardIn(BaseModel):
    name: str = Field(min_length=1)
    model: str = "flagship"
    rw_key: str = ""  # write-only; encrypted at rest, never returned
    min_send_interval: int = 15


class BoardOut(BaseModel):
    id: str
    name: str
    model: str
    rows: int
    cols: int
    rw_key_last4: str
    has_key: bool
    min_send_interval: int
    status: str
    last_painted_at: datetime | None

    @classmethod
    def of(cls, board: Board) -> BoardOut:
        return cls(
            id=board.id,
            name=board.name,
            model=board.model,
            rows=board.rows,
            cols=board.cols,
            rw_key_last4=board.rw_key_last4,
            has_key=bool(board.rw_key_encrypted),
            min_send_interval=board.min_send_interval,
            status=board.status,
            last_painted_at=board.last_painted_at,
        )


class PipelineEntryIn(BaseModel):
    source_type: str = "job"  # job / scene
    job_name: str | None = None
    scene_id: str | None = None
    data_source: str | None = None  # scene entries: a job feeding the scene's data
    duration_seconds: int = Field(default=60, gt=0)
    refresh_seconds: int | None = None


class PipelineEntryOut(BaseModel):
    id: str
    position: int
    source_type: str
    job_name: str | None
    scene_id: str | None
    data_source: str | None
    duration_seconds: int
    refresh_seconds: int | None


class PipelineIn(BaseModel):
    name: str = Field(min_length=1)
    loop: bool = True
    entries: list[PipelineEntryIn] = Field(default_factory=list)


class PipelineOut(BaseModel):
    id: str
    name: str
    loop: bool
    entries: list[PipelineEntryOut]


class BoardRunOut(BaseModel):
    board_id: str
    pipeline_id: str
    state: str
    current_entry_id: str | None
    updated_at: datetime
