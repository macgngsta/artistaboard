"""Registry of available jobs, keyed by name."""

from __future__ import annotations

from .config import Settings
from .jobs.base import Job
from .jobs.clock import ClockJob
from .jobs.muni import MuniJob
from .jobs.sport_highscores import SportHighScoresJob
from .jobs.sport_lowscores import SportLowScoresJob
from .jobs.spotify import SpotifyJob
from .jobs.worldcup import WorldCupJob

JOB_TYPES: dict[str, type[Job]] = {
    ClockJob.name: ClockJob,
    MuniJob.name: MuniJob,
    WorldCupJob.name: WorldCupJob,
    SportHighScoresJob.name: SportHighScoresJob,
    SportLowScoresJob.name: SportLowScoresJob,
    SpotifyJob.name: SpotifyJob,
}


def build_job(name: str, settings: Settings, **overrides: object) -> Job:
    """Instantiate a job by name.

    ``overrides`` derive a per-call :class:`Settings` (via ``model_copy``) so a
    caller can supply per-entry/per-board config — e.g. a pipeline running the
    same job for two boards with different ``worldcup_group`` — without touching
    the process-global ``get_settings()`` singleton. Values are taken as-is (no
    re-validation), so pass already-typed values.
    """
    try:
        job_type = JOB_TYPES[name]
    except KeyError as exc:
        known = ", ".join(sorted(JOB_TYPES))
        raise ValueError(f"unknown job {name!r}; known jobs: {known}") from exc
    if overrides:
        settings = settings.model_copy(update=overrides)
    return job_type(settings)
