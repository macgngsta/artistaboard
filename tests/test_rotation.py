from datetime import datetime, timedelta

from artistaboard.rotation import RotationState, select

NOW = datetime(2026, 6, 28, 14, 0)


def _pick(pool, state, now, *, rotate=300, signal=lambda x: x["v"]):
    chosen, state = select(pool, key=lambda x: x["id"], signal=signal, state=state, now=now, rotate_seconds=rotate)
    return chosen, state


def test_holds_within_window_then_advances():
    a, b = {"id": "a", "v": 0}, {"id": "b", "v": 0}
    state = RotationState()
    first, state = _pick([a, b], state, NOW)
    held, state = _pick([a, b], state, NOW + timedelta(minutes=2))  # within 5 min
    assert held["id"] == first["id"]
    rotated, state = _pick([a, b], state, NOW + timedelta(minutes=6))  # past window
    assert rotated["id"] != first["id"]


def test_signal_change_preempts_immediately():
    a, b = {"id": "a", "v": 0}, {"id": "b", "v": 0}
    state = RotationState()
    first, state = _pick([a, b], state, NOW)
    # b's signal changes before the rotate window elapses -> b wins now
    b2 = {"id": "b", "v": 1}
    after, state = _pick([a, b2], state, NOW + timedelta(minutes=1))
    assert after["id"] == "b"


def test_constant_signal_disables_preemption():
    # A pure time-based playlist: signal never changes, so it only rotates on cadence.
    a, b = {"id": "a", "v": 0}, {"id": "b", "v": 99}
    state = RotationState()
    first, state = _pick([a, b], state, NOW, signal=lambda x: 0)
    held, state = _pick([a, b], state, NOW + timedelta(seconds=30), rotate=60, signal=lambda x: 0)
    assert held["id"] == first["id"]  # held despite differing v, because signal is constant


def test_per_item_rotate_seconds_varies_dwell():
    a, b = {"id": "a", "v": 0}, {"id": "b", "v": 0}
    state = RotationState()
    first, state = _pick([a, b], state, NOW, rotate=120)
    # 90s later with a 120s dwell -> still holding
    held, state = _pick([a, b], state, NOW + timedelta(seconds=90), rotate=120)
    assert held["id"] == first["id"]
    # same elapsed but a 60s dwell -> advances
    state2 = RotationState()
    f2, state2 = _pick([a, b], state2, NOW, rotate=60)
    adv, state2 = _pick([a, b], state2, NOW + timedelta(seconds=90), rotate=60)
    assert adv["id"] != f2["id"]
