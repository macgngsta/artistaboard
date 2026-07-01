"""Registry of available jobs, keyed by name."""

from __future__ import annotations

from typing import Any

from .config import Settings
from .jobs.base import Job, JobOptions
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


def _job_type(name: str) -> type[Job]:
    try:
        return JOB_TYPES[name]
    except KeyError as exc:
        known = ", ".join(sorted(JOB_TYPES))
        raise ValueError(f"unknown job {name!r}; known jobs: {known}") from exc


def job_options_model(name: str) -> type[JobOptions]:
    """The typed options schema a job accepts (``JobOptions`` when it has no knobs)."""
    return _job_type(name).Options


def source_key(name: str, options: dict[str, Any] | None) -> str:
    """The snapshot-series identity for a source given per-entry options — derived
    from only the fetch-defining options, so entries that differ merely in display
    options share one polled series ('' when the source has a single series)."""
    return job_options_model(name).model_validate(options or {}).source_key()


def options_overrides(name: str, options: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a raw per-entry options dict against the job's schema and return the
    :class:`Settings` overrides it implies. Empty options -> no overrides (the entry
    inherits the process-global defaults). Raises ``pydantic.ValidationError`` on a
    bad/unknown option so callers can surface it (the API turns it into a 422)."""
    if not options:
        return {}
    return job_options_model(name).model_validate(options).to_overrides()


def build_job(name: str, settings: Settings, **overrides: object) -> Job:
    """Instantiate a job by name.

    ``overrides`` derive a per-call :class:`Settings` (via ``model_copy``) so a
    caller can supply per-entry/per-board config — e.g. a pipeline running the
    same job for two boards with different ``worldcup_group`` — without touching
    the process-global ``get_settings()`` singleton. Values are taken as-is (no
    re-validation), so pass already-typed values (see :func:`options_overrides`).
    """
    job_type = _job_type(name)
    if overrides:
        settings = settings.model_copy(update=overrides)
    return job_type(settings)
