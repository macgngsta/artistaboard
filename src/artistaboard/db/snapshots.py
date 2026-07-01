"""Read/write helpers for ``data_snapshots``: the poller writes readings, the paint
path reads the most recent one for a source. Append-only — writes never update."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from .models import DataSnapshot


def write_snapshot(
    session: Session,
    source: str,
    payload: dict[str, Any],
    *,
    source_key: str = "",
    fetched_at: datetime | None = None,
) -> DataSnapshot:
    snap = DataSnapshot(
        source=source,
        source_key=source_key,
        payload=payload,
        fetched_at=fetched_at or datetime.now(UTC),
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def latest_snapshot(session: Session, source: str, source_key: str = "") -> DataSnapshot | None:
    """The newest reading for a source (+ fetch-defining key), or None if never polled."""
    return session.exec(
        select(DataSnapshot)
        .where(DataSnapshot.source == source, DataSnapshot.source_key == source_key)
        .order_by(DataSnapshot.fetched_at.desc())
        .limit(1)
    ).first()
