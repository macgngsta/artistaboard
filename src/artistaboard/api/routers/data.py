"""Data-layer HTTP surface: per-source freshness + a manual poll. Thin wrappers over
the poller's pure functions (``referenced_sources`` / ``run_poll_cycle``) and
``latest_snapshot``, scoped to the current user's running boards. See
``docs/plans/active/jobs-management-api.md``."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from ...db.snapshots import latest_snapshot
from ...poller import referenced_sources, run_poll_cycle
from ..deps import CurrentUser, SessionDep, SettingsDep
from ..schemas import DataSourceOut, PollResultOut

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/sources", response_model=list[DataSourceOut])
def list_sources(user: CurrentUser, session: SessionDep) -> list[DataSourceOut]:
    """The distinct data series the user's running boards reference, each with its
    latest-snapshot freshness (``never`` when nothing has been polled yet)."""
    now = datetime.now(UTC)
    out: list[DataSourceOut] = []
    for ref in referenced_sources(session, owner_id=user.id):
        snap = latest_snapshot(session, ref.source, ref.source_key)
        fetched = snap.fetched_at if snap else None
        if fetched is not None and fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)  # SQLite hands back naive datetimes
        out.append(
            DataSourceOut(
                source=ref.source,
                source_key=ref.source_key,
                last_fetched_at=fetched,
                age_seconds=(now - fetched).total_seconds() if fetched else None,
                has_data=snap is not None,
            )
        )
    return out


@router.post("/poll", response_model=PollResultOut)
def poll_now(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> PollResultOut:
    """Poll every source the user's running boards reference, now. Per-source failures
    are isolated. On SQLite/dev this is the only poll path; on Postgres it's a kick
    alongside the scheduled daemon."""
    result = run_poll_cycle(session, settings, owner_id=user.id)
    return PollResultOut(polled=result.polled, failed=result.failed)
