import json

import pytest

from vestaboard import COLS, ROWS, codes
from vestaboard.font import Glyph
from vestaboard.scene import Scene


def _write_grid(path, fill_map):
    """fill_map: dict (r,c)->label; everything else blank."""
    grid = [["." for _ in range(COLS)] for _ in range(ROWS)]
    for (r, c), label in fill_map.items():
        grid[r][c] = label
    path.write_text(json.dumps(grid))
    return path


def test_from_file_parses_regions(tmp_path):
    p = _write_grid(tmp_path / "s.json", {(0, 0): "A", (0, 1): "A", (2, 5): "B"})
    scene = Scene.from_file(p)
    assert set(scene.regions) == {"A", "B"}
    a = scene.regions["A"]
    assert (a.row0, a.col0, a.row1, a.col1) == (0, 0, 0, 1)
    assert a.width == 2 and a.height == 1


def test_string_row_format_parses_like_lists(tmp_path):
    # The human-readable form: 6 strings of 22 chars.
    rows = ["AAAAA.BBBBBBBBBBBBBBBB"] * ROWS
    p = tmp_path / "s.json"
    p.write_text(json.dumps(rows))
    scene = Scene.from_file(p)
    assert set(scene.regions) == {"A", "B"}
    a, b = scene.regions["A"], scene.regions["B"]
    assert (a.row0, a.col0, a.row1, a.col1) == (0, 0, 5, 4)
    assert (b.row0, b.col0, b.row1, b.col1) == (0, 6, 5, 21)


def test_bundled_scene_files_load():
    from vestaboard.config import get_settings

    settings = get_settings()
    assert "A" in Scene.from_file(settings.scenes_dir / "clock.json").regions
    muni = Scene.from_file(settings.scenes_dir / "muni.json")
    assert set(muni.regions) == {"A", "B"}


def test_wrong_width_error_names_the_row(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(["AAA"] * ROWS))  # rows too narrow
    with pytest.raises(ValueError, match="row 0 must be 22"):
        Scene.from_file(p)


def test_object_form_with_grid_key(tmp_path):
    grid = [["A"] * COLS for _ in range(ROWS)]
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"grid": grid, "labels": {"A": "all"}}))
    scene = Scene.from_file(p)
    assert "A" in scene.regions


def test_text_is_offset_within_region(tmp_path):
    p = _write_grid(tmp_path / "s.json", {(1, 3): "A", (1, 4): "A", (1, 5): "A"})
    scene = Scene.from_file(p)
    scene.text("AB", region="A")
    assert scene.grid[1][3] == codes.char_to_code("A")
    assert scene.grid[1][4] == codes.char_to_code("B")


def test_text_clips_at_region_edge(tmp_path):
    p = _write_grid(tmp_path / "s.json", {(0, 0): "A", (0, 1): "A"})
    scene = Scene.from_file(p)
    scene.text("ABCD", region="A")  # region only 2 wide
    assert scene.grid[0][0] == codes.char_to_code("A")
    assert scene.grid[0][1] == codes.char_to_code("B")
    # nothing painted past the region bound
    assert scene.grid[0][2] == codes.BLANK


def test_stamp_only_lights_on_pixels():
    glyph = Glyph.from_flat(2, 2, [1, 0, 0, 1])
    scene = Scene()
    scene.stamp(glyph, 0, 0, on_code=codes.GREEN)
    assert scene.grid[0][0] == codes.GREEN
    assert scene.grid[0][1] == codes.BLANK
    assert scene.grid[1][1] == codes.GREEN


def test_to_characters_validates_shape_and_copies():
    scene = Scene()
    chars = scene.to_characters()
    assert len(chars) == ROWS and all(len(r) == COLS for r in chars)
    chars[0][0] = 5
    assert scene.grid[0][0] == codes.BLANK  # deep copy


def test_set_rejects_out_of_range():
    with pytest.raises(ValueError):
        Scene().set(0, 0, 99)


def test_bad_template_shape_raises(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps([["A", "B"]]))  # not 6x22
    with pytest.raises(ValueError):
        Scene.from_file(p)
