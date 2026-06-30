from datetime import datetime, timedelta

from artistaboard.pipeline import Pipeline, RuntimeEntry
from artistaboard.rotation import RotationState

NOW = datetime(2026, 6, 29, 12, 0)


def _entry(eid, dur):
    return RuntimeEntry(
        id=eid, duration_seconds=dur, refresh_seconds=None, source_type="scene", job_name=None, scene_id=eid
    )


def _fresh(entries):
    return Pipeline("p", entries, loop=True, state=RotationState(index=-1))


def test_starts_at_first_entry():
    p = _fresh([_entry("a", 60), _entry("b", 60)])
    assert p.active(NOW).id == "a"


def test_holds_within_window_then_advances_and_loops():
    p = _fresh([_entry("a", 60), _entry("b", 30)])
    assert p.active(NOW).id == "a"
    assert p.active(NOW + timedelta(seconds=30)).id == "a"  # within a's 60s
    assert p.active(NOW + timedelta(seconds=61)).id == "b"  # a's window elapsed
    assert p.active(NOW + timedelta(seconds=92)).id == "a"  # b's 30s elapsed -> loop to a


def test_seconds_left_counts_down_within_window():
    p = _fresh([_entry("a", 60)])
    e = p.active(NOW)
    assert p.seconds_left(e, NOW + timedelta(seconds=20)) == 60 - 20


def test_rotation_state_round_trips():
    p = _fresh([_entry("a", 60), _entry("b", 60)])
    p.active(NOW)
    restored = RotationState.from_dict(p.state.to_dict())
    assert restored.index == p.state.index
    assert restored.last_switch == p.state.last_switch
    assert restored.current_id == "a"
