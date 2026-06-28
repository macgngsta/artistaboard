from datetime import UTC, datetime

from vestaboard import codes
from vestaboard.config import get_settings
from vestaboard.jobs.muni import MuniJob, parse_arrivals


def _visit(line, iso):
    return {
        "MonitoredVehicleJourney": {
            "LineRef": line,
            "MonitoredCall": {"ExpectedArrivalTime": iso},
        }
    }


def _payload(*visits):
    return {"ServiceDelivery": {"StopMonitoringDelivery": {"MonitoredStopVisit": list(visits)}}}


NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_parse_computes_minutes_sorted_and_filtered():
    payload = _payload(
        _visit("L", "2024-01-01T12:12:00Z"),
        _visit("L", "2024-01-01T12:05:00Z"),
        _visit("N", "2024-01-01T12:03:00Z"),  # different line, filtered out
        _visit("L", "2024-01-01T11:58:00Z"),  # in the past, dropped
    )
    assert parse_arrivals(payload, NOW, line="L") == [5, 12]


def test_parse_handles_list_delivery_and_caps_results():
    payload = {
        "ServiceDelivery": {
            "StopMonitoringDelivery": [
                {
                    "MonitoredStopVisit": [
                        _visit("L", "2024-01-01T12:02:00Z"),
                        _visit("L", "2024-01-01T12:09:00Z"),
                        _visit("L", "2024-01-01T12:15:00Z"),
                        _visit("L", "2024-01-01T12:25:00Z"),
                    ]
                }
            ]
        }
    }
    assert parse_arrivals(payload, NOW, line="L") == [2, 9, 15]  # capped at 3


def test_parse_empty():
    assert parse_arrivals({}, NOW, line="L") == []


def test_render_draws_l_badge_and_minutes():
    scene = MuniJob(get_settings()).render([5, 12])
    chars = scene.to_characters()
    # L badge uses the accent color (green) in region A (left 5 cols)
    assert any(chars[r][c] == codes.GREEN for r in range(6) for c in range(5))
    # the minutes text "5  12" appears somewhere in the right region
    flat = [c for row in chars for c in row]
    assert codes.char_to_code("5") in flat
    assert codes.char_to_code("1") in flat and codes.char_to_code("2") in flat


def test_render_no_data_shows_dashes():
    scene = MuniJob(get_settings()).render([])
    flat = [c for row in scene.to_characters() for c in row]
    assert codes.char_to_code("-") in flat
