"""schedule_ticks wiring, without a real scheduler or wall-clock sleeps: a fake
scheduler records the registration so we can assert the immediate paint + a
non-paused interval job deterministically (the old test slept 2.3s and asserted a
fire count, which was slow and timing-flaky)."""

from artistaboard.__main__ import schedule_ticks


class FakeScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, trigger=None, **kwargs):
        self.jobs.append((func, trigger, kwargs))


def test_schedule_ticks_paints_once_now_and_registers_interval():
    count = [0]

    def tick():
        count[0] += 1

    sched = FakeScheduler()
    assert schedule_ticks(sched, tick, interval_seconds=30) is sched

    assert count[0] == 1  # one immediate paint, no double fire

    assert len(sched.jobs) == 1
    func, trigger, kwargs = sched.jobs[0]
    assert trigger == "interval"
    assert kwargs.get("seconds") == 30
    # Regression guard: the job must NOT be added paused. next_run_time=None adds it
    # paused so it never fires (only the immediate tick would run).
    assert kwargs.get("next_run_time", "unset") is not None

    func()  # the registered callable really is the paint tick
    assert count[0] == 2
