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
# Below this many minutes the big countdown turns red ("catch it now").
IMMINENT_MIN = 5
# The two follow-up arrival rows in scenes/muni.json (the soonest is the headline).
ARRIVAL_REGIONS = ("C", "D")
# Words to drop when shortening a SIRI destination name to fit the board.
_DEST_NOISE = ("METRO", "STATION", "STA")
# SIRI DirectionRef → human label (region G is 7 wide, so "OUTBOUND" is clipped).
_DIRECTIONS = {"IB": "INBOUND", "OB": "OUTBOUND"}


@dataclass(frozen=True)
class MuniArrivals:
    minutes: list[int] = field(default_factory=list)
    destination: str = ""
    direction: str = ""


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
    entries: list[tuple[int, str, str]] = []
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
            direction = _DIRECTIONS.get(str(journey.get("DirectionRef", "")).upper(), "")
            entries.append((round(delta), _clean_destination(journey.get("DestinationName")), direction))
    entries.sort(key=lambda e: e[0])
    entries = entries[:MAX_ARRIVALS]
    if not entries:
        return MuniArrivals()
    return MuniArrivals(minutes=[m for m, _, _ in entries], destination=entries[0][1], direction=entries[0][2])


class MuniJob(Job):
    name = "muni"
    interval_seconds = 30

    @cached_property
    def _font(self) -> Font:
        return Font.from_file(self.settings.font_path)

    @cached_property
    def _badge_font(self) -> Font:
        # 3x3 line letter/number, carved out of the colored badge (region A is 5x5).
        return Font.from_file(self.settings.fonts_dir / "3x3pixels.json")

    @cached_property
    def _score_font(self) -> Font:
        # 3x5 digits fill the two-slot countdown in region B (the gap is letter-spacing).
        return Font.from_file(self.settings.fonts_dir / "3by5.json")

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

        # A: line badge — the route letter carved out of a line-colored block.
        # Falls back to the line's own color (violet for the L) unless overridden.
        badge = self.settings.muni_color
        if badge is None:
            badge = codes.resolve_color(MUNI_LINE_COLORS.get(LINE_LABEL, DEFAULT_LINE_COLOR))
        scene.glyphs(LINE_LABEL, region="A", on_code=codes.BLANK, fill=badge, font=self._badge_font)

        mins = data.minutes
        # B: the soonest arrival as a big 3x5 countdown — red when imminent, else white.
        if mins:
            color = codes.RED if mins[0] < IMMINENT_MIN else codes.WHITE
            scene.glyphs(f"{mins[0]:02d}", region="B", on_code=color, font=self._score_font)

        # C/D: the next two arrivals after the headline as "NN MIN".
        for region, m in zip(ARRIVAL_REGIONS, mins[1:], strict=False):
            scene.text(f"{m:02d} MIN", region=region)

        # E/G/F: static operator label, direction, and final destination.
        scene.text("SFMUNI", region="E")
        scene.text(data.direction, region="G")
        scene.text(data.destination, region="F", align="right")
        return scene
