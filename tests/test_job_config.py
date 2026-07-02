"""Decomposed per-job config: env vars still map to the nested models (backward
compatible names), per-entry overrides splice into the right sub-config without
touching the singleton, and source_key derivation is unchanged."""

from artistaboard.config import Settings
from artistaboard.registry import build_job, options_overrides, source_key


def test_env_vars_map_to_nested_config(monkeypatch):
    # The flat env var names are preserved after decomposition (env_prefix per config).
    monkeypatch.setenv("WORLDCUP_GROUP", "C")
    monkeypatch.setenv("WORLDCUP_ROTATE_SECONDS", "120")
    monkeypatch.setenv("SPORT_LEAGUE", "hockey/nhl")
    monkeypatch.setenv("SPORT_LOWSCORE_LEAGUE", "soccer/eng.1")
    monkeypatch.setenv("MUNI_LINE", "T")
    monkeypatch.setenv("FIVEONEONE_API_KEY", "secret-key")  # shared key, aliased onto MuniConfig
    monkeypatch.setenv("CLOCK_TZ_LABEL", "ET")
    s = Settings(_env_file=None)
    assert (s.worldcup.group, s.worldcup.rotate_seconds) == ("C", 120)
    assert (s.sport.league, s.sport.lowscore_league) == ("hockey/nhl", "soccer/eng.1")
    assert s.muni.line == "T"
    assert s.muni.api_key == "secret-key"
    assert s.clock.tz_label == "ET"


def test_defaults_when_no_env():
    s = Settings(_env_file=None)
    assert s.worldcup.rotate_seconds == 300
    assert s.sport.league == "basketball/nba"
    assert s.muni.line == "L"
    assert s.clock.color == 69  # white
    assert s.spotify.redirect_uri.endswith("/callback")


def test_build_job_override_isolates_the_singleton():
    base = Settings(_env_file=None)
    job = build_job("world_cup", base, **options_overrides("world_cup", {"group": "D", "rotate_seconds": 90}))
    assert job.settings.worldcup.group == "D"
    assert job.settings.worldcup.rotate_seconds == 90
    # Neither the base Settings nor its nested config is mutated.
    assert base.worldcup.group == ""
    assert base.worldcup.rotate_seconds == 300


def test_shared_sport_config_maps_low_league_distinctly():
    base = Settings(_env_file=None)
    low = build_job("sport_lowscores", base, **options_overrides("sport_lowscores", {"league": "baseball/mlb"}))
    high = build_job("sport_highscores", base, **options_overrides("sport_highscores", {"league": "basketball/nba"}))
    # Both read from SportConfig but via different fields, so they don't collide.
    assert low._league() == "baseball/mlb"
    assert high._league() == "basketball/nba"


def test_source_key_unchanged_by_decomposition():
    # Only fetch-defining options split the snapshot series (display options don't).
    assert source_key("world_cup", {"group": "C"}) == ""  # group is display-only
    assert source_key("muni", {"stop_code": "13915", "line": "T"}) == '{"stop_code": "13915"}'
    assert source_key("sport_highscores", {"league": "basketball/nba"}) == '{"league": "basketball/nba"}'
