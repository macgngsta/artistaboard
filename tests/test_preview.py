import pytest

from artistaboard import COLS, ROWS, codes
from artistaboard.preview import render_preview


def _blank():
    return [[codes.BLANK] * COLS for _ in range(ROWS)]


def test_no_color_snapshot_is_deterministic():
    grid = _blank()
    grid[0][0] = codes.char_to_code("L")
    grid[0][1] = codes.GREEN
    out = render_preview(grid, color=False)
    lines = out.splitlines()
    assert lines[0] == "+" + "-" * (COLS * 2) + "+"
    assert lines[0] == lines[-1]
    # 'L' prints as a character cell, color block as '##', both 2 wide.
    assert lines[1].startswith("|L ##")
    assert "\033[" not in out  # no ANSI escapes in no-color mode


def test_color_mode_emits_ansi():
    grid = _blank()
    grid[0][0] = codes.RED
    assert "\033[48;5;" in render_preview(grid, color=True)


def test_wrong_shape_raises():
    with pytest.raises(ValueError):
        render_preview([[0] * COLS])
