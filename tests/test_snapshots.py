"""The data_snapshots store: append-only writes, latest-read per source+key."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from artistaboard.db.engine import create_db_and_tables, get_engine, init_engine
from artistaboard.db.snapshots import latest_snapshot, write_snapshot


def _session(tmp_path) -> Session:
    init_engine(f"sqlite:///{tmp_path}/snap.db")
    create_db_and_tables()
    return Session(get_engine())


def test_latest_returns_the_newest_reading(tmp_path):
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    with _session(tmp_path) as s:
        write_snapshot(s, "world_cup", {"n": 1}, fetched_at=t0)
        write_snapshot(s, "world_cup", {"n": 2}, fetched_at=t0 + timedelta(minutes=1))
        write_snapshot(s, "world_cup", {"n": 3}, fetched_at=t0 + timedelta(minutes=2))
        latest = latest_snapshot(s, "world_cup")
    assert latest is not None
    assert latest.payload == {"n": 3}  # newest by fetched_at, not insert order


def test_latest_is_scoped_by_source_key(tmp_path):
    now = datetime(2026, 6, 1, tzinfo=UTC)
    with _session(tmp_path) as s:
        write_snapshot(s, "muni", {"stop": "A"}, source_key="stopA", fetched_at=now)
        write_snapshot(s, "muni", {"stop": "B"}, source_key="stopB", fetched_at=now)
        assert latest_snapshot(s, "muni", "stopA").payload == {"stop": "A"}
        assert latest_snapshot(s, "muni", "stopB").payload == {"stop": "B"}


def test_latest_is_none_when_never_polled(tmp_path):
    with _session(tmp_path) as s:
        assert latest_snapshot(s, "clock") is None


def test_writes_are_append_only(tmp_path):
    now = datetime(2026, 6, 1, tzinfo=UTC)
    with _session(tmp_path) as s:
        a = write_snapshot(s, "clock", {"t": "1"}, fetched_at=now)
        b = write_snapshot(s, "clock", {"t": "2"}, fetched_at=now + timedelta(minutes=1))
        assert a.id != b.id  # a second write is a new row, not an update


def test_partition_helpers_are_noop_on_sqlite(tmp_path):
    from artistaboard.db.partitions import ensure_partitions, prune_partitions

    with _session(tmp_path) as s:
        assert ensure_partitions(s) == []
        assert prune_partitions(s) == []
