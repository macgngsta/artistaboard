from datetime import UTC, datetime

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.muni import MuniArrivals, MuniJob, parse_stop_monitoring


def _settings(**overrides):
    # Hermetic: ignore the developer's local .env so tests use known defaults.
    return Settings(_env_file=None, **overrides)


def _visit(line, iso, dest="Metro Embarcadero Station"):
    return {
        "MonitoredVehicleJourney": {
            "LineRef": line,
            "DestinationName": dest,
            "MonitoredCall": {"ExpectedArrivalTime": iso},
        }
    }


def _payload(*visits):
    return {"ServiceDelivery": {"StopMonitoringDelivery": {"MonitoredStopVisit": list(visits)}}}


NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_parse_minutes_destination_sorted_and_filtered():
    payload = _payload(
        _visit("L", "2024-01-01T12:12:00Z"),
        _visit("L", "2024-01-01T12:05:00Z"),
        _visit("N", "2024-01-01T12:03:00Z"),  # different line, filtered out
        _visit("L", "2024-01-01T11:58:00Z"),  # in the past, dropped
    )
    result = parse_stop_monitoring(payload, NOW, line="L")
    assert result.minutes == [5, 12]
    assert result.destination == "EMBARCADERO"  # "Metro"/"Station" stripped


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
    assert parse_stop_monitoring(payload, NOW, line="L").minutes == [2, 9, 15]  # capped at 3


def test_parse_empty():
    result = parse_stop_monitoring({}, NOW, line="L")
    assert result.minutes == [] and result.destination == ""


def test_render_populates_all_regions():
    scene = MuniJob(_settings()).render(MuniArrivals(minutes=[8, 25, 33], destination="EMBARCADERO"))
    chars = scene.to_characters()

    # A: violet badge fill + white L glyph
    a = scene.regions["A"]
    a_codes = {chars[r][c] for r in range(a.row0, a.row1 + 1) for c in range(a.col0, a.col1 + 1)}
    assert codes.VIOLET in a_codes and codes.WHITE in a_codes

    # D/E/F: each row carries its minutes + "MIN"
    for region, mins in zip(("D", "E", "F"), (8, 25, 33), strict=True):
        reg = scene.regions[region]
        row = chars[reg.row0]
        assert row[reg.col0 : reg.col0 + 2] == codes.text_to_codes(f"{mins:02d}")
        assert row[reg.col0 + 3 : reg.col0 + 6] == codes.text_to_codes("MIN")

    # C: destination text appears on the bottom row
    flat = [c for r in chars for c in r]
    assert codes.char_to_code("E") in flat and codes.char_to_code("O") in flat


def test_render_no_data_shows_dashes():
    scene = MuniJob(_settings()).render(MuniArrivals(minutes=[], destination=""))
    # "--" renders as big white glyphs in region B; no MIN rows are drawn.
    b = scene.regions["B"]
    assert any(scene.grid[r][c] == codes.WHITE for r in range(b.row0, b.row1 + 1) for c in range(b.col0, b.col1 + 1))
    assert codes.char_to_code("M") not in [c for row in scene.to_characters() for c in row]
