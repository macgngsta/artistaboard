"""Muni job: next SF Muni L Taraval arrivals via the 511.org SIRI API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cached_property

import httpx

from .. import codes
from ..font import Font
from ..scene import Scene
from .base import Job

SIRI_URL = "http://api.511.org/transit/StopMonitoring"
LINE_LABEL = "L"
MAX_ARRIVALS = 3

# Official SF Muni Metro line colors, mapped to the nearest Vestaboard color.
# Used to color the badge so it matches the line (e.g. the L Taraval is purple).
MUNI_LINE_COLORS: dict[str, str] = {
    "J": "yellow",  # Church (tan/olive)
    "K": "blue",  # Ingleside
    "L": "violet",  # Taraval (purple)
    "M": "green",  # Ocean View
    "N": "blue",  # Judah
    "T": "red",  # Third
}
DEFAULT_LINE_COLOR = "violet"
# The three arrival rows in scenes/muni.json, top to bottom.
ARRIVAL_REGIONS = ("D", "E", "F")
# Words to drop when shortening a SIRI destination name to fit the board.
_DEST_NOISE = ("METRO", "STATION", "STA")


@dataclass(frozen=True)
class MuniArrivals:
    minutes: list[int] = field(default_factory=list)
    destination: str = ""


def _clean_destination(name: str | None) -> str:
    if not name:
        return ""
    words = [w for w in name.upper().split() if w not in _DEST_NOISE]
    return " ".join(words)


def parse_stop_monitoring(payload: dict, now: datetime, line: str | None = None) -> MuniArrivals:
    """Extract minutes-until-arrival and the destination from a 511 SIRI response."""
    delivery = payload.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {})
    if isinstance(delivery, list):
        delivery = delivery[0] if delivery else {}
    visits = delivery.get("MonitoredStopVisit", []) or []
    entries: list[tuple[int, str]] = []
    for visit in visits:
        journey = visit.get("MonitoredVehicleJourney", {})
        if line and str(journey.get("LineRef", "")).upper() != line.upper():
            continue
        call = journey.get("MonitoredCall", {})
        expected = call.get("ExpectedArrivalTime")
        if not expected:
            continue
        when = datetime.fromisoformat(expected.replace("Z", "+00:00"))
        delta = (when - now).total_seconds() / 60
        if delta >= 0:
            entries.append((round(delta), _clean_destination(journey.get("DestinationName"))))
    entries.sort(key=lambda e: e[0])
    entries = entries[:MAX_ARRIVALS]
    destination = entries[0][1] if entries else ""
    return MuniArrivals(minutes=[m for m, _ in entries], destination=destination)


class MuniJob(Job):
    name = "muni"
    interval_seconds = 30

    @cached_property
    def _font(self) -> Font:
        return Font.from_file(self.settings.font_path)

    def fetch(self) -> MuniArrivals:
        key = self.settings.fiveoneone_api_key
        stop = self.settings.muni_stop_code
        if not key or not stop:
            raise RuntimeError("muni job needs FIVEONEONE_API_KEY and MUNI_STOP_CODE")
        resp = httpx.get(
            SIRI_URL,
            params={"api_key": key, "agency": "SF", "stopCode": stop, "format": "json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        # 511 serves JSON with a UTF-8 BOM; httpx .json() trips on it.
        payload = httpx.Response(200, content=resp.content.decode("utf-8-sig").encode()).json()
        return parse_stop_monitoring(payload, datetime.now(UTC), line=LINE_LABEL)

    def render(self, data: MuniArrivals) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "muni.json", font=self._font)

        # A: line-colored badge (glyphs) with the route letter, in the display font.
        # Falls back to the line's own color (violet for the L) unless overridden.
        badge = self.settings.muni_color
        if badge is None:
            badge = codes.resolve_color(MUNI_LINE_COLORS.get(LINE_LABEL, DEFAULT_LINE_COLOR))
        scene.glyphs(LINE_LABEL, region="A", on_code=codes.WHITE, fill=badge)

        # B: the soonest arrival as big block glyphs (or "--" when no data).
        headline = f"{data.minutes[0]:02d}" if data.minutes else "--"
        scene.glyphs(headline, region="B", on_code=codes.WHITE)

        # D/E/F: pure alphanumerics — "NN MIN" (the space lands in the gap column).
        for region, mins in zip(ARRIVAL_REGIONS, data.minutes, strict=False):
            scene.text(f"{mins:02d} MIN", region=region)

        # C: destination along the bottom, right-aligned.
        scene.text(data.destination, region="C", align="right")
        return scene
