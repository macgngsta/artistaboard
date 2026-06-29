from datetime import datetime

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.clock import ClockJob


def get_settings():
    return Settings(_env_file=None)


def test_clock_renders_big_time_in_region_b():
    scene = ClockJob(get_settings()).render(datetime(2024, 1, 1, 16, 34))
    b = scene.regions["B"]
    # the big glyphs paint the accent color somewhere inside region B
    assert any(scene.grid[r][c] == codes.WHITE for r in range(b.row0, b.row1 + 1) for c in range(b.col0, b.col1 + 1))


def test_clock_renders_small_time_and_tz_in_region_c():
    scene = ClockJob(get_settings()).render(datetime(2024, 1, 1, 16, 34))
    row5 = scene.grid[5]
    # "16:34" at cols 12-16
    assert row5[12:17] == codes.text_to_codes("16:34")
    # "PT" at cols 19-20
    assert row5[19:21] == codes.text_to_codes("PT")


def test_clock_tz_label_is_configurable(monkeypatch):
    monkeypatch.setenv("CLOCK_TZ_LABEL", "ET")
    scene = ClockJob(Settings(_env_file=None)).render(datetime(2024, 1, 1, 16, 34))
    assert scene.grid[5][19:21] == codes.text_to_codes("ET")
