import pytest
from pydantic import ValidationError

from artistaboard.config import Settings
from artistaboard.jobs.worldcup import WorldCupJob
from artistaboard.registry import build_job, job_options_model, options_overrides


def test_build_job_returns_typed_instance():
    job = build_job("world_cup", Settings(_env_file=None))
    assert isinstance(job, WorldCupJob)


def test_unknown_job_lists_known_names():
    with pytest.raises(ValueError, match="unknown job 'nope'"):
        build_job("nope", Settings(_env_file=None))


def test_overrides_derive_per_call_settings_without_touching_base():
    base = Settings(_env_file=None)
    job = build_job("world_cup", base, worldcup_group="C", worldcup_rotate_seconds=120)
    assert job.settings.worldcup_group == "C"
    assert job.settings.worldcup_rotate_seconds == 120
    # the base settings object is untouched (derived via model_copy)
    assert base.worldcup_group == ""


def test_options_overrides_maps_clean_names_to_settings_fields():
    assert options_overrides("world_cup", {"group": "C", "rotate_seconds": 120, "live_only": True}) == {
        "worldcup_group": "C",
        "worldcup_rotate_seconds": 120,
        "worldcup_live_only": True,
    }


def test_options_overrides_omits_unset_so_settings_stay_the_fallback():
    # An unset option must NOT appear as an override (else it would clobber a
    # deployment-configured default with the option's own default).
    assert options_overrides("world_cup", {"group": "C"}) == {"worldcup_group": "C"}
    assert options_overrides("world_cup", {}) == {}
    assert options_overrides("world_cup", None) == {}


def test_options_overrides_rejects_unknown_key():
    with pytest.raises(ValidationError):
        options_overrides("world_cup", {"bogus": 1})


def test_options_overrides_enforces_field_constraints():
    with pytest.raises(ValidationError):
        options_overrides("world_cup", {"rotate_seconds": 0})  # gt=0


def test_muni_color_option_resolves_name_to_a_code():
    ov = options_overrides("muni", {"line": "L", "color": "violet"})
    assert ov["muni_line"] == "L"
    assert isinstance(ov["muni_color"], int)  # name resolved to a Vestaboard code


def test_sport_low_and_high_map_league_to_distinct_settings_fields():
    assert options_overrides("sport_highscores", {"league": "basketball/nba"}) == {"sport_league": "basketball/nba"}
    assert options_overrides("sport_lowscores", {"league": "baseball/mlb"}) == {"sport_lowscore_league": "baseball/mlb"}


def test_options_apply_through_build_job():
    base = Settings(_env_file=None)
    job = build_job("world_cup", base, **options_overrides("world_cup", {"group": "C"}))
    assert job.settings.worldcup_group == "C"


def test_job_without_options_has_empty_schema():
    schema = job_options_model("spotify").model_json_schema()
    assert schema.get("properties", {}) == {}
