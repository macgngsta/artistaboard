"""Pipeline CRUD. A pipeline is an ordered list of entries, each a built-in job or
a stored scene, held for ``duration_seconds``. Entries are validated on write:
job entries must name a real job; scene entries must reference a scene the user can see.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ...db import Pipeline, PipelineEntry, Scene
from ...registry import JOB_TYPES
from ..deps import CurrentUser, SessionDep
from ..schemas import PipelineEntryIn, PipelineEntryOut, PipelineIn, PipelineOut

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


def _validate_entry(entry: PipelineEntryIn, user_id: str, session: SessionDep) -> None:
    if entry.source_type == "job":
        if entry.job_name not in JOB_TYPES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown job {entry.job_name!r}")
    elif entry.source_type == "scene":
        scene = session.get(Scene, entry.scene_id) if entry.scene_id else None
        if scene is None or (not scene.is_system and scene.owner_id != user_id):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "scene entry references an unknown scene")
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"bad source_type {entry.source_type!r}")


def _out(session: SessionDep, pipeline: Pipeline) -> PipelineOut:
    rows = session.exec(
        select(PipelineEntry).where(PipelineEntry.pipeline_id == pipeline.id).order_by(PipelineEntry.position)
    ).all()
    return PipelineOut(
        id=pipeline.id,
        name=pipeline.name,
        loop=pipeline.loop,
        entries=[PipelineEntryOut.model_validate(r, from_attributes=True) for r in rows],
    )


def _replace_entries(session: SessionDep, pipeline_id: str, entries: list[PipelineEntryIn], user_id: str) -> None:
    for existing in session.exec(select(PipelineEntry).where(PipelineEntry.pipeline_id == pipeline_id)).all():
        session.delete(existing)
    for position, entry in enumerate(entries):
        _validate_entry(entry, user_id, session)
        session.add(
            PipelineEntry(
                pipeline_id=pipeline_id,
                position=position,
                source_type=entry.source_type,
                job_name=entry.job_name,
                scene_id=entry.scene_id,
                duration_seconds=entry.duration_seconds,
                refresh_seconds=entry.refresh_seconds,
            )
        )


def _own_pipeline(session: SessionDep, pipeline_id: str, user_id: str) -> Pipeline:
    pipeline = session.get(Pipeline, pipeline_id)
    if pipeline is None or pipeline.owner_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    return pipeline


@router.get("", response_model=list[PipelineOut])
def list_pipelines(user: CurrentUser, session: SessionDep) -> list[PipelineOut]:
    rows = session.exec(select(Pipeline).where(Pipeline.owner_id == user.id)).all()
    return [_out(session, p) for p in rows]


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(body: PipelineIn, user: CurrentUser, session: SessionDep) -> PipelineOut:
    pipeline = Pipeline(owner_id=user.id, name=body.name, loop=body.loop)
    session.add(pipeline)
    session.flush()  # assign pipeline.id before adding entries
    _replace_entries(session, pipeline.id, body.entries, user.id)
    session.commit()
    session.refresh(pipeline)
    return _out(session, pipeline)


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(pipeline_id: str, user: CurrentUser, session: SessionDep) -> PipelineOut:
    return _out(session, _own_pipeline(session, pipeline_id, user.id))


@router.put("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(pipeline_id: str, body: PipelineIn, user: CurrentUser, session: SessionDep) -> PipelineOut:
    pipeline = _own_pipeline(session, pipeline_id, user.id)
    pipeline.name = body.name
    pipeline.loop = body.loop
    _replace_entries(session, pipeline.id, body.entries, user.id)
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return _out(session, pipeline)


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(pipeline_id: str, user: CurrentUser, session: SessionDep) -> None:
    pipeline = _own_pipeline(session, pipeline_id, user.id)
    for entry in session.exec(select(PipelineEntry).where(PipelineEntry.pipeline_id == pipeline.id)).all():
        session.delete(entry)
    session.delete(pipeline)
    session.commit()
