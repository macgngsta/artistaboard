"""Scene CRUD. A scene's ``document`` is the object-form JSON the renderer consumes;
we validate it by parsing (``Scene.from_dict``) before storing, and derive the list
of envelope variables it needs. Users see their own scenes plus read-only system ones.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_
from sqlmodel import select

from ... import COLS, ROWS
from ...db import Scene as SceneRow
from ...render import scene_variables
from ...scene import Scene as SceneDoc
from ..deps import CurrentUser, SessionDep
from ..schemas import SceneIn, SceneOut

router = APIRouter(prefix="/scenes", tags=["scenes"])


def _validate_document(document: dict | list) -> None:
    try:
        SceneDoc.from_dict(document)
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid scene document: {exc}") from exc


def _owned(scene: SceneRow | None, user_id: str) -> SceneRow:
    if scene is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scene not found")
    if scene.is_system or scene.owner_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your scene")
    return scene


@router.get("", response_model=list[SceneOut])
def list_scenes(user: CurrentUser, session: SessionDep) -> list[SceneOut]:
    rows = session.exec(select(SceneRow).where(or_(SceneRow.owner_id == user.id, SceneRow.is_system))).all()
    return [SceneOut.of(s) for s in rows]


@router.post("", response_model=SceneOut, status_code=status.HTTP_201_CREATED)
def create_scene(body: SceneIn, user: CurrentUser, session: SessionDep) -> SceneOut:
    _validate_document(body.document)
    scene = SceneRow(
        owner_id=user.id,
        name=body.name,
        description=body.description,
        model=body.model,
        rows=ROWS,
        cols=COLS,
        document=body.document,
        required_variables=scene_variables(body.document),
    )
    session.add(scene)
    session.commit()
    session.refresh(scene)
    return SceneOut.of(scene)


@router.get("/{scene_id}", response_model=SceneOut)
def get_scene(scene_id: str, user: CurrentUser, session: SessionDep) -> SceneOut:
    scene = session.get(SceneRow, scene_id)
    if scene is None or (not scene.is_system and scene.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scene not found")
    return SceneOut.of(scene)


@router.put("/{scene_id}", response_model=SceneOut)
def update_scene(scene_id: str, body: SceneIn, user: CurrentUser, session: SessionDep) -> SceneOut:
    scene = _owned(session.get(SceneRow, scene_id), user.id)
    _validate_document(body.document)
    scene.name = body.name
    scene.description = body.description
    scene.model = body.model
    scene.document = body.document
    scene.required_variables = scene_variables(body.document)
    scene.updated_at = datetime.now(UTC)
    session.add(scene)
    session.commit()
    session.refresh(scene)
    return SceneOut.of(scene)


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(scene_id: str, user: CurrentUser, session: SessionDep) -> None:
    scene = _owned(session.get(SceneRow, scene_id), user.id)
    session.delete(scene)
    session.commit()
