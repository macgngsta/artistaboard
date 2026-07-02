from datetime import UTC, datetime

from artistaboard import codes
from artistaboard.config import Settings
from artistaboard.jobs.muni import MuniArrivals, MuniConfig, MuniJob, parse_stop_monitoring


def _settings(**overrides):
    # Hermetic: ignore the developer's local .env so tests use known defaults.
    return Settings(_env_file=None, **overrides)


def _visit(line, iso, dest="Metro Embarcadero Station", direction="IB"):
    return {
        "MonitoredVehicleJourney": {
            "LineRef": line,
            "DestinationName": dest,
            "DirectionRef": direction,
            "MonitoredCall": {"ExpectedArrivalTime": iso},
        }
    }


def _payload(*visits):
    return {"ServiceDelivery": {"StopMonitoringDelivery": {"MonitoredStopVisit": list(visits)}}}


NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_parse_minutes_destination_sorted_and_filtered():
    payload = _payload(
        _visit("L", "2024-01-01T12:12:00Z"),
        _visit("L", "2024-01-01T12:05:00Z", direction="OB"),
        _visit("N", "2024-01-01T12:03:00Z"),  # different line, filtered out
        _visit("L", "2024-01-01T11:58:00Z"),  # in the past, dropped
    )
    result = parse_stop_monitoring(payload, NOW, line="L")
    assert result.minutes == [5, 12]
    assert result.destination == "EMBARCADERO"  # "Metro"/"Station" stripped
    assert result.direction == "OUTBOUND"  # DirectionRef of the soonest arrival


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


def _region_codes(scene, label):
    reg = scene.regions[label]
    return {scene.grid[r][c] for r, c in reg.cells}


def test_render_populates_all_regions():
    scene = MuniJob(_settings()).render(
        MuniArrivals(minutes=[8, 25, 33], destination="EMBARCADERO", direction="INBOUND")
    )
    chars = scene.to_characters()

    # A: violet badge with the route letter carved out in white inside the fill.
    a_codes = _region_codes(scene, "A")
    assert codes.VIOLET in a_codes and codes.WHITE in a_codes

    # B: the soonest arrival (8 >= 5 min) renders as a big WHITE countdown.
    assert codes.WHITE in _region_codes(scene, "B")

    # C/D: the arrival list, led by the soonest (same as the headline), as "NN MIN".
    for region, mins in zip(("C", "D"), (8, 25), strict=True):
        reg = scene.regions[region]
        row = chars[reg.row0]
        assert row[reg.col0 : reg.col0 + 2] == codes.text_to_codes(f"{mins:02d}")
        assert row[reg.col0 + 3 : reg.col0 + 6] == codes.text_to_codes("MIN")

    # E/G/F: operator label, full direction, destination.
    e = scene.regions["E"]
    assert chars[e.row0][e.col0 : e.col0 + 6] == codes.text_to_codes("SFMUNI")
    g = scene.regions["G"]
    assert chars[g.row0][g.col0 : g.col0 + 7] == codes.text_to_codes("INBOUND")
    flat = [c for r in chars for c in r]
    assert codes.char_to_code("E") in flat and codes.char_to_code("O") in flat


def test_render_imminent_arrival_is_red():
    scene = MuniJob(_settings()).render(MuniArrivals(minutes=[3, 12], destination="EMBARCADERO"))
    # Under IMMINENT_MIN (5) the big countdown turns red ("catch it now").
    assert codes.RED in _region_codes(scene, "B")


def test_badge_color_follows_configured_line():
    arrivals = MuniArrivals(minutes=[8], destination="X", direction="IB")
    # The chosen line drives the badge colour: L→violet (default), T→red.
    assert codes.VIOLET in _region_codes(MuniJob(_settings()).render(arrivals), "A")
    assert codes.RED in _region_codes(MuniJob(_settings(muni=MuniConfig(line="T"))).render(arrivals), "A")
    # An explicit muni color still overrides the line colour.
    override = MuniJob(_settings(muni=MuniConfig(line="T", color="green"))).render(arrivals)
    assert codes.GREEN in _region_codes(override, "A")


def test_render_no_data_is_blank_headline():
    scene = MuniJob(_settings()).render(MuniArrivals(minutes=[], destination=""))
    # No arrivals: no countdown glyph in B and the C/D "NN MIN" rows stay blank.
    b_codes = _region_codes(scene, "B")
    assert codes.WHITE not in b_codes and codes.RED not in b_codes
    for region in ("C", "D"):
        assert _region_codes(scene, region) == {codes.BLANK}
