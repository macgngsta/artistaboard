import time

from apscheduler.schedulers.background import BackgroundScheduler

from vestaboard.__main__ import schedule_ticks


def test_schedule_ticks_fires_immediately_and_on_interval():
    count = [0]

    def tick():
        count[0] += 1

    scheduler = schedule_ticks(BackgroundScheduler(), tick, interval_seconds=1)
    scheduler.start()
    try:
        time.sleep(2.3)
    finally:
        scheduler.shutdown(wait=False)
    # one immediate paint + at least two interval fires (regression guard against
    # the job being added paused via next_run_time=None, which gives only 1)
    assert count[0] >= 3
