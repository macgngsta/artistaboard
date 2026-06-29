"""Muni job: next SF Muni Metro arrivals (configurable line) via 511.org SIRI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from .. import codes
from .base import Job

SIRI_URL = "http://api.511.org/transit/StopMonitoring"
MAX_ARRIVALS = 3

# Official SF Muni Metro line colors, mapped to the nearest Vestaboard color.
# The badge takes the configured line's color (e.g. the L Taraval is purple).
MUNI_LINE_COLORS: dict[str, str] = {
    "J": "yellow",  # Church (tan/olive)
    "K": "blue",  # Ingleside
    "L": "violet",  # Taraval (purple)
    "M": "green",  # Ocean View
    "N": "blue",  # Judah
    "T": "red",  # Third
}
DEFAULT_LINE_COLOR = "violet"
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
    scene_name = "muni"

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
        return parse_stop_monitoring(payload, datetime.now(UTC), line=self.settings.muni_line.upper())

    def bind(self, data: MuniArrivals) -> dict[str, Any]:
        # The badge fills with the configured line's own colour (the user picks the
        # line; L→violet, T→red) unless muni_color overrides it; the scene carves
        # the route letter out of it (color: blank).
        line = self.settings.muni_line.upper()
        badge = self.settings.muni_color
        if badge is None:
            badge = codes.resolve_color(MUNI_LINE_COLORS.get(line, DEFAULT_LINE_COLOR))
        env: dict[str, Any] = {
            "line": line,
            "badge_color": badge,
            "operator": "SFMUNI",
            "direction": data.direction,
            "destination": data.destination,
        }
        mins = data.minutes
        if mins:  # soonest arrival is the big countdown; the rest are follow-up rows
            env["countdown"] = f"{mins[0]:02d}"
            env["soonest"] = mins[0]
        for key, m in zip(("arrival1", "arrival2"), mins[1:], strict=False):
            env[key] = f"{m:02d} MIN"
        return env
