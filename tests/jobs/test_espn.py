from datetime import datetime

from artistaboard.jobs.espn import event_sides, parse_iso, to_int


def test_parse_iso_handles_z_suffix_and_bad_input():
    dt = parse_iso("2026-06-29T17:00Z")
    assert isinstance(dt, datetime) and dt.tzinfo is not None
    assert parse_iso("") is None
    assert parse_iso("not-a-date") is None


def test_to_int_coerces_strings_and_defaults_missing_to_zero():
    assert to_int("3") == 3
    assert to_int(5) == 5
    assert to_int(None) == 0
    assert to_int("") == 0
    assert to_int("x") == 0


def test_event_sides_extracts_home_and_away():
    event = {
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "score": "2"},
                    {"homeAway": "away", "score": "1"},
                ]
            }
        ]
    }
    home, away = event_sides(event)
    assert home["score"] == "2" and away["score"] == "1"


def test_event_sides_missing_sides_are_empty_dicts():
    assert event_sides({}) == ({}, {})
    assert event_sides({"competitions": [{"competitors": []}]}) == ({}, {})
