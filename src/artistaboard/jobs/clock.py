"""Clock job: a big HH:MM clock drawn with the 3x4 glyph font.

Declarative: the scene (clock.json) owns the layout and styling; this job only
supplies the data envelope (the time string, a 2-char timezone label, and the
configured clock colour).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import Job


class ClockJob(Job):
    name = "clock"
    interval_seconds = 60
    scene_name = "clock"

    def fetch(self) -> datetime:
        return datetime.now()

    def bind(self, data: datetime) -> dict[str, Any]:
        hhmm = data.strftime("%H:%M")
        return {"time": hhmm, "tz": self.settings.clock_tz_label[:2], "time_color": self.settings.clock_color}
