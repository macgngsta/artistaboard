import pytest

from artistaboard.config import Settings
from artistaboard.jobs.worldcup import WorldCupJob
from artistaboard.registry import build_job


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
