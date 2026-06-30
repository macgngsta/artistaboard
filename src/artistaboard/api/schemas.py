"""Request/response models for the API (kept separate from the DB tables)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field

from ..db.models import Scene


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
