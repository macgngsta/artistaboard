import json

import pytest

from artistaboard.config import get_settings
from artistaboard.font import Font, Glyph


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
    assert font.has(":")


def test_bytesized_uppercase_l_is_clean_full_height():
    font = Font.from_file(get_settings().fonts_dir / "bytesized3x4.json")
    assert _ascii(font.get("L")) == ["#..", "#..", "#..", "###"]


def test_bytesized_has_distinct_upper_and_lowercase():
    font = Font.from_file(get_settings().fonts_dir / "bytesized3x4.json")
    # both cases exist as separate map entries with genuinely different shapes
    for upper, lower in [("A", "a"), ("E", "e"), ("L", "l"), ("Q", "q")]:
        assert font.glyphs[upper].pixels != font.glyphs[lower].pixels


def test_3x3pixels_font_loads_as_3x3():
    font = Font.from_file(get_settings().fonts_dir / "3x3pixels.json")
    assert font.width == 3 and font.height == 3
    assert all(g.width == 3 and g.height == 3 for g in font.glyphs.values())
    assert _ascii(font.get("0")) == ["###", "#.#", "###"]  # the ring digit
    # colon is hand-set to vertical dots so HH:MM clocks render legibly
    assert _ascii(font.get(":")) == [".#.", "...", ".#."]
    assert font.has("A") and font.has("z")


def test_3by5_font_loads_with_clean_digits_and_caps():
    font = Font.from_file(get_settings().fonts_dir / "3by5.json")
    assert font.width == 3 and font.height == 5
    assert _ascii(font.get("0")) == ["###", "#.#", "#.#", "#.#", "###"]  # ring
    assert _ascii(font.get("A")) == [".#.", "#.#", "###", "#.#", "#.#"]
    # lowercase is not bundled — it falls back to the uppercase glyph
    assert font.get("a").pixels == font.get("A").pixels


def test_invalid_structure(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"structure": "bad", "glyphs": {}}))
    with pytest.raises(ValueError):
        Font.from_file(p)
