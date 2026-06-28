"""Glyphs and JSON font maps.

A font file looks like::

    {"structure": "3x4", "glyphs": {"A": [0,1,0, 1,1,1, 1,1,1, 1,0,1], ...}}

``structure`` is ``"<width>x<height>"``; each glyph value is a flattened, row-major
on/off pixel array of length ``width * height``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Glyph:
    width: int
    height: int
    pixels: tuple[tuple[bool, ...], ...]  # [row][col]

    @classmethod
    def from_flat(cls, width: int, height: int, flat: list[int]) -> Glyph:
        if len(flat) != width * height:
            raise ValueError(f"expected {width * height} pixels, got {len(flat)}")
        rows = tuple(tuple(bool(flat[y * width + x]) for x in range(width)) for y in range(height))
        return cls(width=width, height=height, pixels=rows)

    def blank(self) -> bool:
        return not any(any(row) for row in self.pixels)


class Font:
    """A character -> Glyph map loaded from a JSON font file."""

    def __init__(self, width: int, height: int, glyphs: dict[str, Glyph]) -> None:
        self.width = width
        self.height = height
        self.glyphs = glyphs

    @classmethod
    def from_file(cls, path: str | Path) -> Font:
        raw = json.loads(Path(path).read_text())
        width, height = _parse_structure(raw["structure"])
        glyphs = {ch: Glyph.from_flat(width, height, flat) for ch, flat in raw["glyphs"].items()}
        return cls(width=width, height=height, glyphs=glyphs)

    def _lookup(self, ch: str) -> Glyph | None:
        # Exact match first; fall back across case so "L" works whether the font
        # defines upper, lower, or both (and lowercase never clobbers uppercase).
        for key in (ch, ch.upper(), ch.lower()):
            if key in self.glyphs:
                return self.glyphs[key]
        return None

    def get(self, ch: str) -> Glyph:
        glyph = self._lookup(ch)
        if glyph is None:
            raise KeyError(f"font has no glyph for {ch!r}")
        return glyph

    def has(self, ch: str) -> bool:
        return self._lookup(ch) is not None

    def render_text(self, text: str, spacing: int = 1) -> Glyph:
        """Composite a row of glyphs into a single wide glyph (1 blank-col gap default)."""
        glyphs = [self.get(ch) for ch in text]
        if not glyphs:
            return Glyph(width=0, height=self.height, pixels=())
        total_width = sum(g.width for g in glyphs) + spacing * (len(glyphs) - 1)
        rows: list[list[bool]] = [[False] * total_width for _ in range(self.height)]
        x = 0
        for g in glyphs:
            for y in range(self.height):
                for gx in range(g.width):
                    rows[y][x + gx] = g.pixels[y][gx]
            x += g.width + spacing
        return Glyph(width=total_width, height=self.height, pixels=tuple(tuple(r) for r in rows))


def _parse_structure(structure: str) -> tuple[int, int]:
    try:
        w, h = structure.lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid font structure {structure!r}, expected '<w>x<h>'") from exc
