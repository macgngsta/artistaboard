import json

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.render import render_scene
from vestaboard.scene import Scene


def _scene(tmp_path, grid, render, font="bytesized3x4"):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"grid": grid, "font": font, "render": render}))
    return Scene.from_file(p)


def _settings():
    return Settings(_env_file=None)


def _region_codes(scene, label):
    return {scene.grid[r][c] for r, c in scene.regions[label].cells}


GLYPH_GRID = ["AAA###################"] * 4 + ["######################"] * 2


def test_from_file_loads_render_config_and_font_name(tmp_path):
    scene = _scene(tmp_path, GLYPH_GRID, {"A": {"bind": "x", "as": "glyphs"}})
    assert scene.font_name == "bytesized3x4"
    assert scene.render_config["A"] == {"bind": "x", "as": "glyphs"}


def test_text_binding_writes_value(tmp_path):
    grid = ["AAAAAA################"] + ["######################"] * 5
    scene = _scene(tmp_path, grid, {"A": {"bind": "label", "as": "text"}})
    render_scene(scene, {"label": "HI"}, _settings())
    a = scene.regions["A"]
    assert scene.grid[a.row0][a.col0 : a.col0 + 2] == codes.text_to_codes("HI")


def test_glyphs_data_color(tmp_path):
    scene = _scene(tmp_path, GLYPH_GRID, {"A": {"bind": "n", "as": "glyphs", "color": {"data": "c"}}})
    render_scene(scene, {"n": "5", "c": codes.ORANGE}, _settings())
    assert codes.ORANGE in _region_codes(scene, "A")


def test_leader_rule_violet_blue_and_green(tmp_path):
    cfg = {"A": {"bind": "home.score", "as": "glyphs", "color": {"rule": "leader", "team": "home"}}}
    # live + leading -> violet
    live = _scene(tmp_path, GLYPH_GRID, cfg)
    render_scene(live, {"home.score": 2, "away.score": 1, "final": False}, _settings())
    assert codes.VIOLET in _region_codes(live, "A")
    # final + leading -> blue
    final = _scene(tmp_path, GLYPH_GRID, cfg)
    render_scene(final, {"home.score": 2, "away.score": 1, "final": True}, _settings())
    assert codes.BLUE in _region_codes(final, "A")
    # trailing -> white regardless of state
    trail = _scene(tmp_path, GLYPH_GRID, cfg)
    render_scene(trail, {"home.score": 0, "away.score": 1, "final": True}, _settings())
    assert codes.BLUE not in _region_codes(trail, "A") and codes.WHITE in _region_codes(trail, "A")
    # green scheme
    green_cfg = {
        "A": {"bind": "home.score", "as": "glyphs", "color": {"rule": "leader", "team": "home", "scheme": "green"}}
    }
    green = _scene(tmp_path, GLYPH_GRID, green_cfg)
    render_scene(green, {"home.score": 3, "away.score": 1}, _settings())
    assert codes.GREEN in _region_codes(green, "A")


def test_imminent_rule_threshold(tmp_path):
    cfg = {"A": {"bind": "m", "as": "glyphs", "color": {"rule": "imminent", "field": "m", "threshold": 5}}}
    near = _scene(tmp_path, GLYPH_GRID, cfg)
    render_scene(near, {"m": 3}, _settings())
    assert codes.RED in _region_codes(near, "A")
    far = _scene(tmp_path, GLYPH_GRID, cfg)
    render_scene(far, {"m": 9}, _settings())
    assert codes.RED not in _region_codes(far, "A") and codes.WHITE in _region_codes(far, "A")


def test_fill_paints_region_without_binding(tmp_path):
    grid = ["AAAAA#################"] + ["######################"] * 5
    scene = _scene(tmp_path, grid, {"A": {"as": "fill", "color": "green"}})
    render_scene(scene, {}, _settings())
    assert _region_codes(scene, "A") == {codes.GREEN}


def test_missing_or_empty_value_skips_region(tmp_path):
    grid = ["AAAAAA################"] + ["######################"] * 5
    scene = _scene(tmp_path, grid, {"A": {"bind": "label", "as": "text"}})
    render_scene(scene, {"label": ""}, _settings())  # empty -> untouched
    assert _region_codes(scene, "A") == {codes.BLANK}


def test_transform_upper(tmp_path):
    grid = ["AAAA##################"] + ["######################"] * 5
    scene = _scene(tmp_path, grid, {"A": {"bind": "t", "as": "text", "transform": "upper"}})
    render_scene(scene, {"t": "abcd"}, _settings())
    a = scene.regions["A"]
    assert scene.grid[a.row0][a.col0 : a.col0 + 4] == codes.text_to_codes("ABCD")
