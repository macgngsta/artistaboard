"""The Scene: a 6x22 board model with named regions, loaded from JSON.

A scene template is a JSON array of 6 rows. Each cell is a single region label
(``"A"``-``"Z"``) or one of ``.`` / space / ``#`` for filler (unassigned). Using
``#`` lets you draw borders and gaps that visually read as walls. Same-labeled
cells form a named region with a bounding box you can stamp content into.

The preferred, human-readable form is **6 strings of 22 characters** — the file
literally looks like the board::

    [
      "AAAAA.BBBBBBBBBBBBBBBB",
      "AAAAA.BBBBBBBBBBBBBBBB",
      ... 4 more rows ...
    ]

A row may also be a list of single-character strings (``["A", "A", ...]``); both
parse identically. An object form is accepted too::

    {"grid": [...], "labels": {"A": "clock"}}

where ``labels`` gives human-friendly names (the canonical key stays the letter).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import COLS, ROWS
from . import codes as codes_mod
from .font import Font, Glyph

_ALIGN = ("left", "center", "right")

# Characters that mark a cell as filler/blank (not part of any region).
_UNASSIGNED = {"", ".", " ", "#"}


@dataclass(frozen=True)
class Region:
    label: str
    cells: tuple[tuple[int, int], ...]
    row0: int
    col0: int
    row1: int
    col1: int

    @property
    def height(self) -> int:
        return self.row1 - self.row0 + 1

    @property
    def width(self) -> int:
        return self.col1 - self.col0 + 1


class Scene:
    """A mutable 6x22 grid of Vestaboard character codes plus named regions."""

    def __init__(self, regions: dict[str, Region] | None = None, font: Font | None = None) -> None:
        self.grid: list[list[int]] = [[codes_mod.BLANK] * COLS for _ in range(ROWS)]
        self.regions: dict[str, Region] = regions or {}
        self.font = font  # default font for glyphs(); each call may override it
        # Declarative render config (object-form scenes): region -> binding cfg,
        # plus the named default font. Consumed by artistaboard.render.render_scene.
        self.render_config: dict[str, dict] = {}
        self.font_name: str | None = None

    @classmethod
    def from_file(cls, path: str | Path, font: Font | None = None) -> Scene:
        raw = json.loads(Path(path).read_text())
        is_obj = isinstance(raw, dict)
        grid = raw["grid"] if is_obj else raw
        scene = cls(regions=_parse_regions(grid), font=font)
        if is_obj:
            scene.render_config = raw.get("render", {})
            scene.font_name = raw.get("font")
        return scene

    # -- placement -------------------------------------------------------------
    def _origin(self, region: str | None) -> tuple[int, int, int, int]:
        if region is None:
            return 0, 0, ROWS - 1, COLS - 1
        r = self.regions[region]
        return r.row0, r.col0, r.row1, r.col1

    @staticmethod
    def _align_offset(span: int, content: int, align: str) -> int:
        if align == "center":
            return max(0, (span - content) // 2)
        if align == "right":
            return max(0, span - content)
        return 0

    def set(self, r: int, c: int, code: int) -> Scene:
        if not codes_mod.is_valid_code(code):
            raise ValueError(f"code {code} out of range 0-71")
        if 0 <= r < ROWS and 0 <= c < COLS:
            self.grid[r][c] = code
        return self

    def fill(self, code: int, region: str | None = None) -> Scene:
        """Fill a region's actual labeled cells (not its bounding box), so
        non-rectangular shapes like a rounded badge keep their outline."""
        if region is None:
            cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
        else:
            cells = list(self.regions[region].cells)
        for r, c in cells:
            self.set(r, c, code)
        return self

    def write(self, s: str, region: str | None = None, r: int = 0, align: str = "left") -> Scene:
        """Like :meth:`text` but truncates ``s`` to the region width first."""
        _, c0, _, c1 = self._origin(region)
        return self.text(s[: c1 - c0 + 1], region=region, r=r, align=align)

    def textbox(self, s: str, region: str | None = None, align: str = "left") -> Scene:
        """Word-wrap ``s`` across the region's rows (truncating overflow)."""
        r0, c0, r1, c1 = self._origin(region)
        width, height = c1 - c0 + 1, r1 - r0 + 1
        lines: list[str] = []
        line = ""
        for word in s.split():
            candidate = f"{line} {word}".strip()
            if len(candidate) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word[:width]
        if line:
            lines.append(line)
        for i, text in enumerate(lines[:height]):
            self.text(text, region=region, r=i, align=align)
        return self

    def text(self, s: str, r: int = 0, c: int = 0, region: str | None = None, align: str = "left") -> Scene:
        """Render ``s`` as **pure alphanumerics** (one native character per cell)
        within ``region``, optionally aligned ``left``/``center``/``right``."""
        r0, c0, r1, c1 = self._origin(region)
        c += self._align_offset(c1 - c0 + 1, len(s), align)
        for i, code in enumerate(codes_mod.text_to_codes(s)):
            col, row = c0 + c + i, r0 + r
            if col > c1 or row > r1:
                break
            self.set(row, col, code)
        return self

    def glyphs(
        self,
        s: str,
        region: str | None = None,
        *,
        on_code: int = codes_mod.WHITE,
        fill: int | None = None,
        align: str = "center",
        spacing: int = 1,
        font: Font | None = None,
        invert: bool = False,
    ) -> Scene:
        """Render ``s`` as an **array of big block glyphs** within ``region``,
        using ``font`` (or the scene's default). Lit pixels become ``on_code``;
        ``fill`` optionally paints the region background first (e.g. a badge);
        ``invert`` swaps on/off so the letters are carved out of the fill."""
        font = font or self.font
        if font is None:
            raise ValueError("glyphs() needs a font; pass Scene.from_file(..., font=...) or font=")
        if fill is not None:
            self.fill(fill, region)
        glyph = font.render_text(s, spacing=spacing)
        if invert:
            glyph = glyph.inverted()
        r0, c0, r1, c1 = self._origin(region)
        r = self._align_offset(r1 - r0 + 1, glyph.height, "center")
        c = self._align_offset(c1 - c0 + 1, glyph.width, align)
        return self.stamp(glyph, r, c, on_code=on_code, region=region)

    def stamp(
        self, glyph: Glyph, r: int = 0, c: int = 0, on_code: int = codes_mod.WHITE, region: str | None = None
    ) -> Scene:
        """Stamp a glyph; lit pixels become ``on_code``, off pixels are transparent."""
        r0, c0, r1, c1 = self._origin(region)
        for y in range(glyph.height):
            for x in range(glyph.width):
                if not glyph.pixels[y][x]:
                    continue
                row, col = r0 + r + y, c0 + c + x
                if r0 <= row <= r1 and c0 <= col <= c1:
                    self.set(row, col, on_code)
        return self

    def to_characters(self) -> list[list[int]]:
        """Return a validated 6x22 deep copy for sending to the board."""
        if len(self.grid) != ROWS or any(len(row) != COLS for row in self.grid):
            raise ValueError("scene grid must be 6x22")
        for row in self.grid:
            for code in row:
                if not codes_mod.is_valid_code(code):
                    raise ValueError(f"code {code} out of range 0-71")
        return [row[:] for row in self.grid]


def _parse_regions(grid: list[list[str]]) -> dict[str, Region]:
    if len(grid) != ROWS:
        raise ValueError(f"scene template must have {ROWS} rows, got {len(grid)}")
    for r, row in enumerate(grid):
        if len(row) != COLS:
            raise ValueError(f"scene row {r} must be {COLS} cells wide, got {len(row)}: {row!r}")
    cells: dict[str, list[tuple[int, int]]] = {}
    for r, row in enumerate(grid):
        for c, label in enumerate(row):
            label = str(label).strip()
            if label in _UNASSIGNED:
                continue
            cells.setdefault(label.upper(), []).append((r, c))
    regions: dict[str, Region] = {}
    for label, pts in cells.items():
        rows = [p[0] for p in pts]
        cols = [p[1] for p in pts]
        regions[label] = Region(
            label=label,
            cells=tuple(pts),
            row0=min(rows),
            col0=min(cols),
            row1=max(rows),
            col1=max(cols),
        )
    return regions
