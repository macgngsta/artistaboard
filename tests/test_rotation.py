from datetime import datetime, timedelta

from artistaboard.rotation import rotate_index

NOW = datetime(2026, 6, 28, 14, 0, 0)


def test_holds_within_bucket_then_advances():
    i0 = rotate_index(3, NOW, 60)
    # Still inside the same 60s bucket -> same item.
    assert rotate_index(3, NOW + timedelta(seconds=30), 60) == i0
    # Next bucket -> advances one step (mod count).
    assert rotate_index(3, NOW + timedelta(seconds=60), 60) == (i0 + 1) % 3


def test_wraps_modulo_count():
    seq = [rotate_index(2, NOW + timedelta(seconds=60 * k), 60) for k in range(4)]
    # Alternates and wraps: whatever the first index is, it flips each bucket.
    assert seq == [seq[0], (seq[0] + 1) % 2, seq[0], (seq[0] + 1) % 2]


def test_single_item_is_always_zero():
    assert rotate_index(1, NOW, 60) == 0
    assert rotate_index(1, NOW + timedelta(hours=3), 300) == 0


def test_longer_cadence_holds_longer():
    i0 = rotate_index(4, NOW, 300)
    # 90s in, a 300s cadence still holds; a 60s cadence would have moved on.
    assert rotate_index(4, NOW + timedelta(seconds=90), 300) == i0
