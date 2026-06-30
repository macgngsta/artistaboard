"""Shared rotation selector for "show one of N items, switch on a cadence".

Several jobs cycle a board through a pool of items (live matches, live games),
holding each for a few minutes and switching sooner when something noteworthy
changes (a score). The policy is identical across them, so it lives here once:

* a **priority signal** change in any pool item wins the board immediately;
* otherwise hold the current item until ``rotate_seconds`` elapses;
* then advance round-robin.

``select`` is pure given its ``RotationState``: it reads ``now`` rather than the
clock, so callers can freeze time in tests, and the state is a plain record so it
can later be persisted (e.g. to resume a running pipeline across a restart).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class RotationState:
    """Mutable rotation bookkeeping. Carried by the caller across ``select`` calls.

    JSON-round-trippable (``to_dict``/``from_dict``) so a runner can persist it and
    resume mid-rotation after a restart.
    """

    index: int = 0
    last_switch: datetime | None = None
    current_id: str | None = None
    signals: dict[str, Hashable] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "last_switch": self.last_switch.isoformat() if self.last_switch else None,
            "current_id": self.current_id,
            "signals": dict(self.signals),
        }

    @classmethod
    def from_dict(cls, data: dict) -> RotationState:
        raw = data.get("last_switch")
        return cls(
            index=data.get("index", 0),
            last_switch=datetime.fromisoformat(raw) if raw else None,
            current_id=data.get("current_id"),
            signals=dict(data.get("signals") or {}),
        )


def select[T](
    pool: Sequence[T],
    *,
    key: Callable[[T], str],
    signal: Callable[[T], Hashable],
    state: RotationState,
    now: datetime,
    rotate_seconds: float,
) -> tuple[T, RotationState]:
    """Pick which item of ``pool`` to show now, mutating and returning ``state``.

    ``pool`` must be non-empty (callers filter to a pool first and handle empty
    themselves). ``key`` gives each item a stable id; ``signal`` returns the value
    whose *change* preempts the rotation (return a constant to disable preemption,
    e.g. for a pure time-based playlist). ``rotate_seconds`` is the dwell time for
    the current item — pass the active entry's own duration to vary it per item.
    """
    by_id = {key(item): item for item in pool}
    # An item whose signal differs from what we last recorded wins immediately.
    # A never-seen item defaults to its own current signal, so it is not "changed".
    changed = [item for item in pool if state.signals.get(key(item), signal(item)) != signal(item)]
    for item in pool:
        state.signals[key(item)] = signal(item)

    rotate = timedelta(seconds=rotate_seconds)
    if changed:
        chosen = changed[0]
        state.last_switch = now
    elif state.current_id in by_id and state.last_switch and now - state.last_switch < rotate:
        chosen = by_id[state.current_id]  # hold current
    else:
        state.index = (state.index + 1) % len(pool)
        chosen = pool[state.index]
        state.last_switch = now
    state.current_id = key(chosen)
    return chosen, state
