"""Rotation helpers for cycling a board through a pool of items.

Two independent mechanisms live here:

* :class:`RotationState` — the *pipeline*'s persisted entry cursor (which entry of a
  pipeline shows now), carried across ticks in ``BoardRun.rotation_state`` so a run
  resumes mid-rotation after a restart. The pipeline runner owns it.
* :func:`rotate_index` — a *stateless* item selector for a job's own pool (which of N
  live matches / games to show now). Derived from wall-clock time alone, so it advances
  across paints with no persisted cursor and is trivially testable by freezing ``now``.

The split matters because a job is rebuilt from scratch every paint (``build_job``), so
it cannot carry rotation state in memory; deriving the item from ``now`` sidesteps that.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RotationState:
    """Mutable rotation bookkeeping. Carried by the caller across selections.

    JSON-round-trippable (``to_dict``/``from_dict``) so a runner can persist it and
    resume mid-rotation after a restart.
    """

    index: int = 0
    last_switch: datetime | None = None
    current_id: str | None = None
    signals: dict[str, Hashable] = field(default_factory=dict)
    # Nested-pipeline substates, keyed by the parent entry id whose sub-pipeline they
    # track, so one BoardRun.rotation_state carries the whole tree.
    children: dict[str, RotationState] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "last_switch": self.last_switch.isoformat() if self.last_switch else None,
            "current_id": self.current_id,
            "signals": dict(self.signals),
            "children": {k: v.to_dict() for k, v in self.children.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> RotationState:
        raw = data.get("last_switch")
        return cls(
            index=data.get("index", 0),
            last_switch=datetime.fromisoformat(raw) if raw else None,
            current_id=data.get("current_id"),
            signals=dict(data.get("signals") or {}),
            children={k: cls.from_dict(v) for k, v in (data.get("children") or {}).items()},
        )


def rotate_index(count: int, now: datetime, rotate_seconds: float) -> int:
    """Which of ``count`` items to show at ``now``, advancing every ``rotate_seconds``.

    Stateless and pure: the position is a function of wall-clock time alone, so it moves
    forward across paints without any persisted cursor and is deterministic under a
    frozen ``now`` in tests. ``count`` must be >= 1 and ``rotate_seconds`` > 0.
    """
    return int(now.timestamp() // rotate_seconds) % count
