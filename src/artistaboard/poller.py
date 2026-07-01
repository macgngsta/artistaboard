"""Postgres-backed poller: on a schedule, fetch every *referenced* source's full
dataset into ``data_snapshots`` so the paint path reads the DB, never an API.

Orchestrated by Procrastinate (jobs / workers / retries / periodic cron on Postgres —
no Redis). The poll *logic* (:func:`referenced_sources`, :func:`run_poll_cycle`) is a
plain, SQLite-testable function; the Procrastinate app + periodic task are a thin
Postgres-only wrapper run as the ``artistaboard poll`` daemon.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlmodel import Session, select

from .config import Settings, get_settings
from .db.engine import get_engine, init_engine
from .db.migrate import run_migrations
from .db.models import BoardRun, PipelineEntry
from .db.partitions import ensure_partitions, prune_partitions
from .db.snapshots import write_snapshot
from .registry import JOB_TYPES, build_job, options_overrides, source_key

log = logging.getLogger(__name__)


# -- poll logic (engine-agnostic, unit-tested on SQLite) -------------------------
@dataclass(frozen=True)
class SourceRef:
    """A distinct snapshot series to poll: a source + its fetch-defining identity."""

    source: str
    source_key: str
    options: dict


def referenced_sources(session: Session) -> list[SourceRef]:
    """The distinct ``(source, source_key)`` pairs referenced by *running* boards'
    pipelines — we only poll data something is actually showing. Deduped so a source
    used by many entries/boards is polled once per fetch-defining identity."""
    runs = session.exec(select(BoardRun).where(BoardRun.state == "running")).all()
    pipeline_ids = {r.pipeline_id for r in runs}
    if not pipeline_ids:
        return []
    entries = session.exec(select(PipelineEntry).where(PipelineEntry.pipeline_id.in_(pipeline_ids))).all()
    seen: dict[tuple[str, str], SourceRef] = {}
    for e in entries:
        source = e.job_name if e.source_type == "job" else e.data_source
        if not source or source not in JOB_TYPES:
            continue  # scene entries without a data_source have nothing to poll
        key = source_key(source, e.options)
        seen.setdefault((source, key), SourceRef(source, key, e.options or {}))
    return list(seen.values())


@dataclass
class PollResult:
    polled: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def run_poll_cycle(session: Session, settings: Settings) -> PollResult:
    """Poll every referenced source once, writing a snapshot each. A single source's
    failure (a flaky API, a missing key) is isolated so the rest of the cycle runs."""
    result = PollResult()
    for ref in referenced_sources(session):
        try:
            job = build_job(ref.source, settings, **options_overrides(ref.source, ref.options))
            write_snapshot(session, ref.source, job.poll(), source_key=ref.source_key)
            result.polled.append(f"{ref.source}:{ref.source_key}")
        except Exception as exc:  # noqa: BLE001 — one bad source must not sink the cycle
            log.warning("poll failed for %s (key=%r): %s", ref.source, ref.source_key, exc)
            result.failed.append((ref.source, str(exc)))
    return result


# -- Procrastinate wiring (Postgres only) ----------------------------------------
def _conninfo(settings: Settings) -> str:
    """Procrastinate's psycopg connector wants a libpq DSN, not SQLAlchemy's
    ``postgresql+psycopg://`` form."""
    url = settings.database_url
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix) :]
    return url


def build_app(settings: Settings):
    """The Procrastinate app with the periodic poll task registered. Imported lazily
    so the SQLite-testable logic above never depends on Procrastinate/Postgres."""
    from procrastinate import App, PsycopgConnector

    app = App(connector=PsycopgConnector(conninfo=_conninfo(settings)))

    @app.periodic(cron=settings.poll_cron)
    @app.task(name="poll_sources", queue="poll", retry=2)
    def poll_sources(timestamp: int) -> None:
        with Session(get_engine()) as session:
            ensure_partitions(session)  # cover month rollover between deploys
            result = run_poll_cycle(session, settings)
        log.info("poll cycle: %d polled, %d failed", len(result.polled), len(result.failed))

    return app


def _ensure_procrastinate_schema(app, engine) -> None:
    from sqlalchemy import inspect

    if "procrastinate_jobs" not in inspect(engine).get_table_names():
        app.schema_manager.apply_schema()  # first run: install Procrastinate's tables


def run_poll_daemon(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    if not settings.database_url.startswith("postgresql"):
        raise SystemExit("the poller requires Postgres (set DATABASE_URL=postgresql+psycopg://...)")
    engine = init_engine(settings.database_url)
    run_migrations(settings.database_url)  # our schema (data_snapshots)
    with Session(engine) as session:
        ensure_partitions(session)
        prune_partitions(session)
    app = build_app(settings)
    with app.open():
        _ensure_procrastinate_schema(app, engine)
    log.info("poll daemon starting (cron=%r)", settings.poll_cron)
    app.run_worker()
    return 0
