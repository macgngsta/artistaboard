"""Partition date math (engine-independent). The DDL itself runs only on Postgres."""

from datetime import date

from artistaboard.db.partitions import (
    _next_month,
    _parse_partition_month,
    _partition_name,
)


def test_next_month_rolls_over_year_end():
    assert _next_month(date(2026, 12, 1)) == date(2027, 1, 1)
    assert _next_month(date(2026, 1, 1)) == date(2026, 2, 1)
    assert _next_month(date(2026, 2, 1)) == date(2026, 3, 1)  # short month


def test_partition_name_is_month_stamped():
    assert _partition_name(date(2026, 7, 1)) == "data_snapshots_2026_07"


def test_parse_partition_month_roundtrips():
    assert _parse_partition_month("data_snapshots_2026_07") == date(2026, 7, 1)
    assert _parse_partition_month("public.data_snapshots_2026_07") == date(2026, 7, 1)


def test_parse_ignores_the_default_catch_all():
    # The DEFAULT partition has no month and must never be pruned.
    assert _parse_partition_month("data_snapshots_default") is None
