"""Muni job: next SF Muni L Taraval arrivals via the 511.org SIRI API."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cached_property

import httpx

from ..font import Font
from ..scene import Scene
from .base import Job

SIRI_URL = "http://api.511.org/transit/StopMonitoring"
LINE_LABEL = "L"
MAX_ARRIVALS = 3


def parse_arrivals(payload: dict, now: datetime, line: str | None = None) -> list[int]:
    """Extract minutes-until-arrival from a 511 SIRI StopMonitoring response."""
    delivery = payload.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {})
    if isinstance(delivery, list):
        delivery = delivery[0] if delivery else {}
    visits = delivery.get("MonitoredStopVisit", []) or []
    mins: list[int] = []
    for visit in visits:
        journey = visit.get("MonitoredVehicleJourney", {})
        if line and str(journey.get("LineRef", "")).upper() != line.upper():
            continue
        expected = journey.get("MonitoredCall", {}).get("ExpectedArrivalTime")
        if not expected:
            continue
        when = datetime.fromisoformat(expected.replace("Z", "+00:00"))
        delta = (when - now).total_seconds() / 60
        if delta >= 0:
            mins.append(round(delta))
    return sorted(mins)[:MAX_ARRIVALS]


class MuniJob(Job):
    name = "muni"
    interval_seconds = 30

    @cached_property
    def _font(self) -> Font:
        return Font.from_file(self.settings.font_path)

    def fetch(self) -> list[int]:
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
        return parse_arrivals(payload, datetime.now(UTC), line=LINE_LABEL)

    def render(self, data: list[int]) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "muni.json")
        scene.stamp_centered(self._font.get("L"), on_code=self.settings.muni_color, region="A")
        text = "  ".join(str(m) for m in data) if data else "--"
        scene.text(text, r=2, c=1, region="B")
        return scene
