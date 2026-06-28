from datetime import datetime

from vestaboard import codes
from vestaboard.config import get_settings
from vestaboard.jobs.clock import ClockJob
from vestaboard.preview import render_preview


def test_clock_renders_hhmm_glyphs():
    scene = ClockJob(get_settings()).render(datetime(2024, 1, 1, 9, 41))
    chars = scene.to_characters()
    lit = {c for row in chars for c in row}
    # only the accent color (white) and blank should appear
    assert lit <= {codes.BLANK, codes.WHITE}
    assert codes.WHITE in lit


def test_clock_preview_snapshot():
    scene = ClockJob(get_settings()).render(datetime(2024, 1, 1, 9, 41))
    out = render_preview(scene.to_characters(), color=False)
    # 5 glyph columns (0 9 : 4 1) leave a recognizable, stable picture
    assert out == "\n".join(
        [
            "+--------------------------------------------+",
            "|                                            |",
            "|    ##    ######    ##    ##  ##  ##        |",
            "|  ##  ##  ######          ######    ##      |",
            "|    ##        ##    ##        ##    ##      |",
            "|                                            |",
            "|                                            |",
            "+--------------------------------------------+",
        ]
    )
