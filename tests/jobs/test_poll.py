"""The poll layer: each source's full normalized dataset as a JSON snapshot payload,
and the fetch-defining source_key that groups snapshot series. Network-free — the
HTTP-bound poll() wrappers are thin over the parse functions exercised here."""

import json
from datetime import UTC, datetime

from artistaboard.jobs.base import jsonable
from artistaboard.jobs.muni import parse_stop_full
from artistaboard.jobs.worldcup import parse_espn
from artistaboard.registry import source_key


# -- source_key: only fetch-defining options split a series ----------------------
def test_source_key_uses_only_fetch_defining_options():
    # Muni: the stop defines the series; line/color are display-only.
    a = source_key("muni", {"stop_code": "15551", "line": "L"})
    b = source_key("muni", {"stop_code": "15551", "line": "N", "color": "red"})
    assert a == b  # same stop, different display -> same series
    assert source_key("muni", {"stop_code": "99999"}) != a  # different stop -> different series


def test_source_key_empty_when_no_fetch_defining_options():
    # World Cup is one endpoint; group is a display filter, so every entry shares it.
    assert source_key("world_cup", {"group": "C"}) == ""
    assert source_key("world_cup", {}) == ""


def test_source_key_is_stable_and_json():
    k = source_key("sport_highscores", {"league": "basketball/nba"})
    assert json.loads(k) == {"league": "basketball/nba"}


# -- full-dataset serialization --------------------------------------------------
def test_worldcup_payload_serializes_all_matches_json_safe():
    events = [
        {
            "id": str(i),
            "date": "2026-06-29T17:00Z",
            "season": {"slug": "group-stage"},
            "status": {"type": {"state": "pre"}},
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "score": "0", "team": {"displayName": "A", "abbreviation": "A"}},
                        {"homeAway": "away", "score": "0", "team": {"displayName": "B", "abbreviation": "B"}},
                    ]
                }
            ],
        }
        for i in range(3)
    ]
    payload = {"matches": jsonable(parse_espn(events))}
    assert len(payload["matches"]) == 3  # ALL matches, not one selected
    assert isinstance(payload["matches"][0]["kickoff"], str)  # datetime -> iso string
    json.dumps(payload)  # must be JSON-serializable end to end


def test_muni_full_parse_keeps_every_line_and_direction():
    def visit(line, iso, direction):
        return {
            "MonitoredVehicleJourney": {
                "LineRef": line,
                "DestinationName": "Embarcadero",
                "DirectionRef": direction,
                "MonitoredCall": {"ExpectedArrivalTime": iso},
            }
        }

    now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    payload = {
        "ServiceDelivery": {
            "StopMonitoringDelivery": {
                "MonitoredStopVisit": [
                    visit("L", "2024-01-01T12:12:00Z", "IB"),
                    visit("N", "2024-01-01T12:05:00Z", "OB"),
                    visit("L", "2024-01-01T12:03:00Z", "OB"),
                    visit("N", "2024-01-01T11:58:00Z", "IB"),  # past -> dropped
                ]
            }
        }
    }
    full = parse_stop_full(payload, now)
    lines = {(a["line"], a["direction"]) for a in full["arrivals"]}
    assert lines == {("L", "INBOUND"), ("N", "OUTBOUND"), ("L", "OUTBOUND")}  # all kept, no line filter
    assert all(a["minutes"] >= 0 for a in full["arrivals"])
    json.dumps(full)


def test_poll_default_raises_for_a_source_without_polling():
    import pytest

    from artistaboard.config import Settings
    from artistaboard.jobs.base import Job

    class Bare(Job):
        name = "bare"
        interval_seconds = 60

        def fetch(self):
            return None

    with pytest.raises(NotImplementedError):
        Bare(Settings(_env_file=None)).poll()
