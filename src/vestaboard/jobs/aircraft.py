"""Aircraft job (stub): planes overhead and how far away they are.

Sketch for the full implementation:
  - Query a free ADS-B source for a bounding box around (AIRCRAFT_LAT, AIRCRAFT_LON):
      GET https://opensky-network.org/api/states/all?lamin=&lomin=&lamax=&lomax=
    (anonymous) or https://opendata.adsb.fi/api/v2/lat/<lat>/lon/<lon>/dist/<km>
  - Pick the nearest aircraft, compute great-circle distance from the box center.
  - render() draws the callsign + distance (e.g. "UAL123  4MI") into a region.
Registered here so it is selectable from the CLI/registry once implemented.
"""

from __future__ import annotations

from typing import Any

from ..scene import Scene
from .base import Job


class AircraftJob(Job):
    name = "aircraft"
    interval_seconds = 60

    def fetch(self) -> Any:
        raise NotImplementedError("aircraft job is not implemented yet")

    def render(self, data: Any) -> Scene:
        raise NotImplementedError("aircraft job is not implemented yet")
