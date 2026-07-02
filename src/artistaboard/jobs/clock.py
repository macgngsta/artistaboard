"""Clock job: a big HH:MM clock drawn with the 3x4 glyph font.

Declarative: the scene (clock.json) owns the layout and styling; this job only
supplies the data envelope (the time string, a 2-char timezone label, and the
configured clock colour).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from .. import codes
from .base import ColorOption, Job, JobOptions


class ClockConfig(BaseSettings):
    """Clock job config (env: CLOCK_*)."""

    model_config = SettingsConfigDict(env_prefix="CLOCK_", env_file=".env", extra="ignore")
    color: ColorOption = codes.WHITE
    tz_label: str = "PT"  # 2-char corner label (e.g. PT/ET)


class ClockOptions(JobOptions):
    tz_label: str | None = None  # 2-char corner label (e.g. PT/ET)
    color: ColorOption = None


class ClockJob(Job):
    name = "clock"
    interval_seconds = 60
    scene_name = "clock"
    Options = ClockOptions
    config_attr = "clock"

    def fetch(self) -> datetime:
        return datetime.now()

    def poll(self) -> dict[str, Any]:
        # The clock's "full data" is just the moment; render formats it (tz/label).
        return {"iso": datetime.now().isoformat()}

    def from_snapshot(self, payload: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(payload["iso"])

    def bind(self, data: datetime) -> dict[str, Any]:
        hhmm = data.strftime("%H:%M")
        return {"time": hhmm, "tz": self.settings.clock.tz_label[:2], "time_color": self.settings.clock.color}
