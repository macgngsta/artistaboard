"""Muni job: next SF Muni Metro arrivals (configurable line) via 511.org SIRI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from .. import codes
from .base import ColorOption, Job, JobOptions

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


def parse_stop_full(payload: dict, now: datetime) -> dict[str, Any]:
    """Every upcoming arrival at the stop, across all lines and directions — the full
    dataset the poller stores. The render path filters this to the lines/directions a
    board shows, so which line/direction is displayed can change without a re-fetch."""
    delivery = payload.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {})
    if isinstance(delivery, list):
        delivery = delivery[0] if delivery else {}
    visits = delivery.get("MonitoredStopVisit", []) or []
    arrivals: list[dict[str, Any]] = []
    for visit in visits:
        journey = visit.get("MonitoredVehicleJourney", {})
        expected = journey.get("MonitoredCall", {}).get("ExpectedArrivalTime")
        if not expected:
            continue
        delta = (datetime.fromisoformat(expected.replace("Z", "+00:00")) - now).total_seconds() / 60
        if delta < 0:
            continue
        arrivals.append(
            {
                "line": str(journey.get("LineRef", "")).upper(),
                "direction": _DIRECTIONS.get(str(journey.get("DirectionRef", "")).upper(), ""),
                "destination": _clean_destination(journey.get("DestinationName")),
                "minutes": round(delta),
            }
        )
    arrivals.sort(key=lambda a: (a["line"], a["direction"], a["minutes"]))
    return {"arrivals": arrivals, "polled_at": now.isoformat()}


class MuniOptions(JobOptions):
    stop_code: str | None = None  # 511 stop code to monitor
    line: str | None = None  # route letter (J/K/L/M/N/T); picks the badge color
    color: ColorOption = None  # override the line's own badge color
    override_map: ClassVar[dict[str, str]] = {
        "stop_code": "muni_stop_code",
        "line": "muni_line",
        "color": "muni_color",
    }
    # The stop defines what to poll; line/color are display-only (one stop's snapshot
    # serves every line shown from it), so only the stop splits the snapshot series.
    fetch_defining: ClassVar[frozenset[str]] = frozenset({"stop_code"})


class MuniJob(Job):
    name = "muni"
    interval_seconds = 30
    Options = MuniOptions
    # The "transit" scene is operator-agnostic (badge + countdown + arrivals +
    # operator/direction/destination), so a future NYC-MTA job can reuse it by
    # binding the same envelope — the way the sport jobs share a layout shape.
    scene_name = "transit"

    def _stop_payload(self) -> dict:
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
        return httpx.Response(200, content=resp.content.decode("utf-8-sig").encode()).json()

    def fetch(self) -> MuniArrivals:
        return parse_stop_monitoring(self._stop_payload(), datetime.now(UTC), line=self.settings.muni_line.upper())

    def poll(self) -> dict[str, Any]:
        # All lines/directions at the stop; the render path filters to what's shown.
        return parse_stop_full(self._stop_payload(), datetime.now(UTC))

    def from_snapshot(self, payload: dict[str, Any]) -> MuniArrivals:
        # Select this board's line from the full stop snapshot — same shape fetch()
        # returns (soonest first, capped), but with no re-fetch.
        line = self.settings.muni_line.upper()
        rows = sorted(
            (a for a in payload.get("arrivals", []) if str(a.get("line", "")).upper() == line),
            key=lambda a: a["minutes"],
        )[:MAX_ARRIVALS]
        if not rows:
            return MuniArrivals()
        return MuniArrivals(
            minutes=[a["minutes"] for a in rows], destination=rows[0]["destination"], direction=rows[0]["direction"]
        )

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
        if mins:  # soonest arrival is the big countdown and also leads the side list
            env["countdown"] = f"{mins[0]:02d}"
            env["soonest"] = mins[0]
        for key, m in zip(("arrival1", "arrival2"), mins, strict=False):
            env[key] = f"{m:02d} MIN"
        return env
