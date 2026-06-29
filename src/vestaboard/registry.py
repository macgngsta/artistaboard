"""Registry of available jobs, keyed by name."""

from __future__ import annotations

from .config import Settings
from .jobs.aircraft import AircraftJob
from .jobs.base import Job
from .jobs.clock import ClockJob
from .jobs.muni import MuniJob
from .jobs.worldcup import WorldCupJob

JOB_TYPES: dict[str, type[Job]] = {
    ClockJob.name: ClockJob,
    MuniJob.name: MuniJob,
    WorldCupJob.name: WorldCupJob,
    AircraftJob.name: AircraftJob,
}


def build_job(name: str, settings: Settings) -> Job:
    try:
        job_type = JOB_TYPES[name]
    except KeyError as exc:
        known = ", ".join(sorted(JOB_TYPES))
        raise ValueError(f"unknown job {name!r}; known jobs: {known}") from exc
    return job_type(settings)
