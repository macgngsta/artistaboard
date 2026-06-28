"""Clock job: a big HH:MM clock drawn with the 3x4 glyph font."""

from __future__ import annotations

from datetime import datetime
from functools import cached_property

from ..font import Font
from ..scene import Scene
from .base import Job


class ClockJob(Job):
    name = "clock"
    interval_seconds = 60

    @cached_property
    def _font(self) -> Font:
        return Font.from_file(self.settings.font_path)

    def fetch(self) -> datetime:
        return datetime.now()

    def render(self, data: datetime) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "clock.json")
        glyph = self._font.render_text(data.strftime("%H:%M"))
        scene.stamp_centered(glyph, on_code=self.settings.clock_color, region="A")
        return scene
