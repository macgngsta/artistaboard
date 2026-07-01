"""Pipeline runner: which entry shows on a board now, and how to render it.

A pipeline is an ordered list of entries, each held for ``duration_seconds`` then
advanced round-robin (looping). The "which entry now" decision reuses the shared
``rotation.select`` with a constant signal (pure time-based rotation) and the
*current* entry's duration as the dwell — so each entry can hold for a different
length. ``Pipeline`` is pure given its ``RotationState`` (freeze ``now`` in tests);
``render_entry`` turns the chosen entry into a Scene by reusing the existing job
build path or the stored-scene render path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from .config import Settings
from .db.models import Pipeline as PipelineRow
from .db.models import PipelineEntry as EntryRow
from .db.models import Scene as SceneRow
from .db.snapshots import latest_snapshot
from .jobs.base import Job
from .registry import build_job, options_overrides, source_key
from .render import render_scene
from .rotation import RotationState
from .scene import Scene


@dataclass
class RuntimeEntry:
    id: str
    duration_seconds: int
    refresh_seconds: int | None
    source_type: str  # job / scene
    job_name: str | None
    scene_id: str | None
    data_source: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    def __init__(self, pipeline_id: str, entries: list[RuntimeEntry], loop: bool, state: RotationState) -> None:
        self.id = pipeline_id
        self.entries = entries
        self.loop = loop
        self.state = state
        self.completed = False

    def _is_current(self) -> bool:
        return self.state.index >= 0 and self.state.current_id in {e.id for e in self.entries}

    def _switch_to(self, index: int, now: datetime) -> RuntimeEntry:
        entry = self.entries[index]
        self.state.index = index
        self.state.last_switch = now
        self.state.current_id = entry.id
        return entry

    def active(self, now: datetime) -> RuntimeEntry | None:
        """The entry to show at ``now``, or ``None`` when a non-looping pipeline has
        finished its last entry (``self.completed`` is then set; the caller stops the
        run and leaves the last frame up). Pipelines step purely on time — no
        preemption — so this is explicit and loop-aware rather than the job selector.
        Mutates ``self.state``; the pool must be non-empty."""
        if not self._is_current():
            return self._switch_to(0, now)  # fresh start (or a stale resume) -> entry 0
        if self.seconds_left(self.entries[self.state.index], now) > 0:
            return self.entries[self.state.index]  # hold the current entry
        nxt = self.state.index + 1
        if nxt >= len(self.entries):
            if not self.loop:
                self.completed = True
                return None
            nxt = 0
        return self._switch_to(nxt, now)

    def seconds_left(self, entry: RuntimeEntry, now: datetime) -> float:
        """How long until the current entry's window elapses (0 if already due)."""
        if self.state.last_switch is None:
            return float(entry.duration_seconds)
        elapsed = (now - self.state.last_switch).total_seconds()
        return max(0.0, entry.duration_seconds - elapsed)


def load_pipeline(session: Session, pipeline_id: str, rotation_state: dict | None) -> Pipeline:
    pipeline = session.get(PipelineRow, pipeline_id)
    loop = pipeline.loop if pipeline is not None else True
    rows = session.exec(select(EntryRow).where(EntryRow.pipeline_id == pipeline_id).order_by(EntryRow.position)).all()
    entries = [
        RuntimeEntry(
            id=r.id,
            duration_seconds=r.duration_seconds,
            refresh_seconds=r.refresh_seconds,
            source_type=r.source_type,
            job_name=r.job_name,
            scene_id=r.scene_id,
            data_source=r.data_source,
            options=r.options or {},
        )
        for r in rows
    ]
    # A fresh run starts at index -1 so the first tick advances to entry 0.
    state = RotationState.from_dict(rotation_state) if rotation_state else RotationState(index=-1)
    return Pipeline(pipeline_id, entries, loop, state)


def _source_data(session: Session, job: Job, source: str, options: dict) -> object:
    """The job's selected data, read from the latest data_snapshot for this source
    (the poller keeps it fresh), falling back to a live ``fetch()`` on a miss — a
    cold start, no poller running, or a job that doesn't support snapshot reads."""
    snap = latest_snapshot(session, source, source_key(source, options))
    if snap is not None:
        try:
            return job.from_snapshot(snap.payload)
        except NotImplementedError:
            pass
    return job.fetch()


def render_entry(entry: RuntimeEntry, settings: Settings, session: Session) -> Scene:
    """Render one entry to a Scene. Source data comes from the latest data_snapshot
    (see :func:`_source_data`), so the paint path reads the DB rather than calling an
    API; a scene entry fills its variables from ``data_source``'s bound envelope, or
    renders static when there's no source."""
    if entry.source_type == "job":
        if not entry.job_name:
            raise ValueError("job entry missing job_name")
        job = build_job(entry.job_name, settings, **options_overrides(entry.job_name, entry.options))
        return job.render(_source_data(session, job, entry.job_name, entry.options))
    if entry.source_type == "scene":
        row = session.get(SceneRow, entry.scene_id)
        if row is None:
            raise ValueError(f"scene {entry.scene_id} not found")
        scene = Scene.from_dict(row.document)
        envelope: dict = {}
        if entry.data_source:
            job = build_job(entry.data_source, settings, **options_overrides(entry.data_source, entry.options))
            envelope = job.bind(_source_data(session, job, entry.data_source, entry.options)) or {}
        render_scene(scene, envelope, settings)
        return scene
    raise ValueError(f"unknown entry source_type {entry.source_type!r}")
