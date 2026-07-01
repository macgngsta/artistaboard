"""Shared helpers for ESPN public scoreboard feeds.

The World Cup and sport-score jobs all read ESPN's site-API scoreboard JSON,
which shares an event envelope: a ``competitions[0].competitors[]`` list keyed by
``homeAway``, ISO date strings, and string scores. These factor out that envelope
parsing; each job still maps it into its own dataclass and runs its own selection
(the shapes and selection rules differ too much to share beyond this).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_iso(value: str) -> datetime | None:
    """Parse an ESPN ISO timestamp (e.g. ``2026-06-29T17:00Z``) to a tz-aware
    datetime, or ``None`` when it's absent or malformed."""
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def to_int(value: Any) -> int:
    """Best-effort int — ESPN scores arrive as strings; missing/blank -> 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def event_sides(event: dict) -> tuple[dict, dict]:
    """The ``(home, away)`` competitor dicts from an ESPN event; a missing side
    is an empty dict."""
    comp = (event.get("competitions") or [{}])[0]
    sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
    return sides.get("home", {}), sides.get("away", {})
