"""Postgres RANGE-partition management for ``data_snapshots`` (no-op on other engines).

``data_snapshots`` is partitioned monthly by ``fetched_at``. We create partitions
ahead of time (the current month plus a couple out) so inserts always land in a real
partition, and prune partitions whose whole month is older than the retention window
with a cheap ``DROP TABLE`` (the design target is ~1 year of 1-minute readings).

The date math is engine-independent and unit-tested; the DDL only runs on Postgres.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session

RETAIN_DAYS = 365
_PARTITION_RE = re.compile(r"data_snapshots_(\d{4})_(\d{2})$")


def _is_postgres(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _next_month(d: date) -> date:
    # d is a month-start; jump into the month then snap to the 1st of the next one.
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _partition_name(month_start: date) -> str:
    return f"data_snapshots_{month_start:%Y_%m}"


def _parse_partition_month(name: str) -> date | None:
    """The month a partition covers, or None for non-monthly partitions (e.g. the
    DEFAULT catch-all, which we never prune)."""
    m = _PARTITION_RE.search(name)
    return date(int(m.group(1)), int(m.group(2)), 1) if m else None


def ensure_partitions(session: Session, *, now: datetime | None = None, months_ahead: int = 2) -> list[str]:
    """Create the current month's partition and ``months_ahead`` future ones if absent.
    Returns the partition names ensured (empty on non-Postgres). Idempotent."""
    if not _is_postgres(session):
        return []
    now = now or datetime.now(UTC)
    ensured: list[str] = []
    start = _month_start(now.date())
    for _ in range(months_ahead + 1):
        nxt = _next_month(start)
        name = _partition_name(start)
        session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF data_snapshots "
                f"FOR VALUES FROM ('{start:%Y-%m-%d}') TO ('{nxt:%Y-%m-%d}')"
            )
        )
        ensured.append(name)
        start = nxt
    session.commit()
    return ensured


def prune_partitions(session: Session, *, now: datetime | None = None, retain_days: int = RETAIN_DAYS) -> list[str]:
    """Drop monthly partitions whose entire month predates the retention cutoff.
    Returns the dropped partition names (empty on non-Postgres)."""
    if not _is_postgres(session):
        return []
    now = now or datetime.now(UTC)
    cutoff = _month_start((now - timedelta(days=retain_days)).date())
    rows = session.execute(
        text("SELECT inhrelid::regclass::text FROM pg_inherits WHERE inhparent = 'data_snapshots'::regclass")
    ).all()
    dropped: list[str] = []
    for (qualified,) in rows:
        month = _parse_partition_month(qualified.split(".")[-1])
        if month is not None and _next_month(month) <= cutoff:  # whole month is older than the window
            session.execute(text(f"DROP TABLE IF EXISTS {qualified}"))
            dropped.append(qualified)
    session.commit()
    return dropped
