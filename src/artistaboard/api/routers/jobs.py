"""Jobs catalogue. Lists the built-in jobs and the JSON Schema of the typed options
each accepts, so the UI can render a per-entry options form and validate input the
same way the pipeline write path does (registry.options_overrides)."""

from __future__ import annotations

from fastapi import APIRouter

from ...registry import JOB_TYPES
from ..deps import CurrentUser
from ..schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(user: CurrentUser) -> list[JobOut]:
    return [
        JobOut(name=name, options_schema=job_type.Options.model_json_schema())
        for name, job_type in sorted(JOB_TYPES.items())
    ]
