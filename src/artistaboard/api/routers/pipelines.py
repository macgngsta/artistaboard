"""Pipeline CRUD. A pipeline is an ordered list of entries, each a built-in job or
a stored scene, held for ``duration_seconds``. Entries are validated on write:
job entries must name a real job; scene entries must reference a scene the user can see.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from sqlmodel import select

from ...db import Pipeline, PipelineEntry, Scene
from ...registry import JOB_TYPES, options_overrides
from ..deps import CurrentUser, SessionDep, get_owned
from ..schemas import PipelineEntryIn, PipelineEntryOut, PipelineIn, PipelineOut

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


def _validate_options(job: str, options: dict) -> None:
    try:
        options_overrides(job, options)  # validates against the job's Options schema
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid options for {job!r}: {exc}") from exc


def _sub_pipeline_ids(session: SessionDep, pipeline_id: str) -> list[str]:
    rows = session.exec(
        select(PipelineEntry).where(PipelineEntry.pipeline_id == pipeline_id, PipelineEntry.source_type == "pipeline")
    ).all()
    return [r.sub_pipeline_id for r in rows if r.sub_pipeline_id]


def _reaches(session: SessionDep, start_id: str, target_id: str, seen: set[str]) -> bool:
    """Whether ``target_id`` is reachable from ``start_id`` by following committed
    sub-pipeline edges — used to reject an entry ``pipeline_id -> sub`` when ``sub``
    can already reach ``pipeline_id`` (a cycle)."""
    if start_id == target_id:
        return True
    if start_id in seen:
        return False
    seen.add(start_id)
    return any(_reaches(session, sid, target_id, seen) for sid in _sub_pipeline_ids(session, start_id))


def _validate_entry(entry: PipelineEntryIn, pipeline_id: str, user_id: str, session: SessionDep) -> None:
    if entry.source_type == "job":
        if entry.job_name not in JOB_TYPES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown job {entry.job_name!r}")
        _validate_options(entry.job_name, entry.options)
    elif entry.source_type == "scene":
        scene = session.get(Scene, entry.scene_id) if entry.scene_id else None
        if scene is None or (not scene.is_system and scene.owner_id != user_id):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "scene entry references an unknown scene")
        if entry.data_source is not None and entry.data_source not in JOB_TYPES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown data_source {entry.data_source!r}")
        if entry.options and entry.data_source is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "options require a data_source job to apply to")
        if entry.data_source is not None:
            _validate_options(entry.data_source, entry.options)
    elif entry.source_type == "pipeline":
        if not entry.sub_pipeline_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "pipeline entry requires a sub_pipeline_id")
        sub = session.get(Pipeline, entry.sub_pipeline_id)
        if sub is None or sub.owner_id != user_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "pipeline entry references an unknown pipeline")
        if _reaches(session, entry.sub_pipeline_id, pipeline_id, set()):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "pipeline entry would create a cycle")
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"bad source_type {entry.source_type!r}")


def _to_out(pipeline: Pipeline, rows: list[PipelineEntry]) -> PipelineOut:
    return PipelineOut(
        id=pipeline.id,
        name=pipeline.name,
        loop=pipeline.loop,
        entries=[PipelineEntryOut.model_validate(r, from_attributes=True) for r in rows],
    )


def _out(session: SessionDep, pipeline: Pipeline) -> PipelineOut:
    rows = session.exec(
        select(PipelineEntry).where(PipelineEntry.pipeline_id == pipeline.id).order_by(PipelineEntry.position)
    ).all()
    return _to_out(pipeline, rows)


def _replace_entries(session: SessionDep, pipeline_id: str, entries: list[PipelineEntryIn], user_id: str) -> None:
    # Update in place by position rather than delete-all-then-reinsert, so entry ids
    # survive edits that don't shrink the list. A running board's BoardRun points at
    # an entry id, so churning ids on every PUT (e.g. a rename) would silently
    # disrupt its rotation.
    # Validate the whole set first, against the committed graph, so cycle detection
    # isn't confused by half-written rows from an autoflush mid-loop.
    for entry in entries:
        _validate_entry(entry, pipeline_id, user_id, session)
    existing = session.exec(
        select(PipelineEntry).where(PipelineEntry.pipeline_id == pipeline_id).order_by(PipelineEntry.position)
    ).all()
    for position, entry in enumerate(entries):
        row = existing[position] if position < len(existing) else PipelineEntry(pipeline_id=pipeline_id)
        row.position = position
        row.source_type = entry.source_type
        row.job_name = entry.job_name
        row.scene_id = entry.scene_id
        row.sub_pipeline_id = entry.sub_pipeline_id
        row.data_source = entry.data_source
        row.options = entry.options
        row.duration_seconds = entry.duration_seconds
        row.refresh_seconds = entry.refresh_seconds
        session.add(row)
    for stale in existing[len(entries) :]:
        session.delete(stale)


def _own_pipeline(session: SessionDep, pipeline_id: str, user_id: str) -> Pipeline:
    return get_owned(session, Pipeline, pipeline_id, user_id, not_found="pipeline not found")


@router.get("", response_model=list[PipelineOut])
def list_pipelines(user: CurrentUser, session: SessionDep) -> list[PipelineOut]:
    rows = session.exec(select(Pipeline).where(Pipeline.owner_id == user.id)).all()
    if not rows:
        return []
    entries = session.exec(
        select(PipelineEntry)
        .where(PipelineEntry.pipeline_id.in_([p.id for p in rows]))
        .order_by(PipelineEntry.pipeline_id, PipelineEntry.position)
    ).all()
    by_pipeline: dict[str, list[PipelineEntry]] = {}
    for entry in entries:
        by_pipeline.setdefault(entry.pipeline_id, []).append(entry)
    return [_to_out(p, by_pipeline.get(p.id, [])) for p in rows]


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
