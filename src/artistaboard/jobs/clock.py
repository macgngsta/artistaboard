"""Clock job: a big HH:MM clock drawn with the 3x4 glyph font.

Declarative: the scene (clock.json) owns the layout and styling; this job only
supplies the data envelope (the time string, a 2-char timezone label, and the
configured clock colour).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from .base import ColorOption, Job, JobOptions


class ClockOptions(JobOptions):
    tz_label: str | None = None  # 2-char corner label (e.g. PT/ET)
    color: ColorOption = None
    override_map: ClassVar[dict[str, str]] = {"tz_label": "clock_tz_label", "color": "clock_color"}


class ClockJob(Job):
    name = "clock"
    interval_seconds = 60
    scene_name = "clock"
    Options = ClockOptions

    def fetch(self) -> datetime:
        return datetime.now()

    def poll(self) -> dict[str, Any]:
        # The clock's "full data" is just the moment; render formats it (tz/label).
        return {"iso": datetime.now().isoformat()}

    def from_snapshot(self, payload: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(payload["iso"])

    def bind(self, data: datetime) -> dict[str, Any]:
        hhmm = data.strftime("%H:%M")
        return {"time": hhmm, "tz": self.settings.clock_tz_label[:2], "time_color": self.settings.clock_color}
