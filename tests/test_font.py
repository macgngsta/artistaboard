import json

import pytest

from vestaboard.config import get_settings
from vestaboard.font import Font, Glyph


def _nanofont() -> Font:
    return Font.from_file(get_settings().fonts_dir / "nanofont3x4.json")


def _ascii(glyph: Glyph) -> list[str]:
    return ["".join("#" if p else "." for p in row) for row in glyph.pixels]


def test_glyph_from_flat_shape():
    g = Glyph.from_flat(3, 4, [1] * 12)
    assert g.width == 3 and g.height == 4
    with pytest.raises(ValueError):
        Glyph.from_flat(3, 4, [1] * 11)


def test_nanofont_known_glyphs():
    font = _nanofont()
    assert font.width == 3 and font.height == 4
    assert _ascii(font.get("0")) == [".#.", "#.#", ".#.", "..."]
    assert _ascii(font.get("1")) == ["#..", ".#.", ".#.", "..."]
    assert _ascii(font.get("A")) == [".#.", "###", "#.#", "..."]
    assert _ascii(font.get("L")) == ["#..", "#..", "###", "..."]
    assert _ascii(font.get(":")) == [".#.", "...", ".#.", "..."]


def test_lowercase_does_not_clobber_uppercase():
    font = _nanofont()
    # 'l' and 'L' have distinct nanofont glyphs.
    assert _ascii(font.get("L")) == ["#..", "#..", "###", "..."]


def test_render_text_width_and_spacing():
    font = _nanofont()
    glyph = font.render_text("12", spacing=1)
    assert glyph.height == 4
    assert glyph.width == 3 + 1 + 3  # two 3-wide glyphs + 1 gap


def test_get_missing_raises():
    font = _nanofont()
    with pytest.raises(KeyError):
        font.get("\t")


def test_bytesized_font_loads_and_has_digits():
    font = Font.from_file(get_settings().fonts_dir / "bytesized3x4.json")
    assert font.width == 3 and font.height == 4
    assert _ascii(font.get("0")) == ["###", "#.#", "#.#", "###"]
    assert _ascii(font.get("1")) == ["##.", ".#.", ".#.", "###"]
    assert font.has(":")


def test_invalid_structure(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"structure": "bad", "glyphs": {}}))
    with pytest.raises(ValueError):
        Font.from_file(p)
