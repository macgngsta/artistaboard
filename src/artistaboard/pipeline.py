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

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from .config import Settings
from .db.models import PipelineEntry as EntryRow
from .db.models import Scene as SceneRow
from .registry import build_job
from .render import render_scene
from .rotation import RotationState
from .rotation import select as rotate_select
from .scene import Scene


@dataclass
class RuntimeEntry:
    id: str
    duration_seconds: int
    refresh_seconds: int | None
    source_type: str  # job / scene
    job_name: str | None
    scene_id: str | None


class Pipeline:
    def __init__(self, pipeline_id: str, entries: list[RuntimeEntry], loop: bool, state: RotationState) -> None:
        self.id = pipeline_id
        self.entries = entries
        self.loop = loop
        self.state = state

    def active(self, now: datetime) -> RuntimeEntry:
        """The entry to show at ``now``. Mutates ``self.state``; pool must be non-empty."""
        # Dwell comes from the entry currently held, so each entry's duration applies.
        rotate_seconds = self.entries[self.state.index].duration_seconds
        chosen, self.state = rotate_select(
            self.entries,
            key=lambda e: e.id,
            signal=lambda e: 0,  # constant -> never preempt; pure time rotation
            state=self.state,
            now=now,
            rotate_seconds=rotate_seconds,
        )
        return chosen

    def seconds_left(self, entry: RuntimeEntry, now: datetime) -> float:
        """How long until the current entry's window elapses (0 if already due)."""
        if self.state.last_switch is None:
            return float(entry.duration_seconds)
        elapsed = (now - self.state.last_switch).total_seconds()
        return max(0.0, entry.duration_seconds - elapsed)


def load_pipeline(session: Session, pipeline_id: str, loop: bool, rotation_state: dict | None) -> Pipeline:
    rows = session.exec(select(EntryRow).where(EntryRow.pipeline_id == pipeline_id).order_by(EntryRow.position)).all()
    entries = [
        RuntimeEntry(
            id=r.id,
            duration_seconds=r.duration_seconds,
            refresh_seconds=r.refresh_seconds,
            source_type=r.source_type,
            job_name=r.job_name,
            scene_id=r.scene_id,
        )
        for r in rows
    ]
    # A fresh run starts at index -1 so the first tick advances to entry 0.
    state = RotationState.from_dict(rotation_state) if rotation_state else RotationState(index=-1)
    return Pipeline(pipeline_id, entries, loop, state)


def render_entry(entry: RuntimeEntry, settings: Settings, session: Session) -> Scene:
    """Render one entry to a Scene. A job entry builds via its own job; a scene entry
    renders the stored document (static envelope for now — data binding lands in a
    later phase)."""
    if entry.source_type == "job":
        if not entry.job_name:
            raise ValueError("job entry missing job_name")
        return build_job(entry.job_name, settings).build()
    if entry.source_type == "scene":
        row = session.get(SceneRow, entry.scene_id)
        if row is None:
            raise ValueError(f"scene {entry.scene_id} not found")
        scene = Scene.from_dict(row.document)
        render_scene(scene, {}, settings)
        return scene
    raise ValueError(f"unknown entry source_type {entry.source_type!r}")
