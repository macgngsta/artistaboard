"""The Scene: a 6x22 board model with named regions, loaded from JSON.

A scene template is a JSON array of 6 rows. Each cell is a single region label
(``"A"``-``"Z"``) or ``.`` / a space for unassigned. Same-labeled cells form a
named region with a bounding box you can stamp content into.

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
from .font import Glyph

_UNASSIGNED = {"", ".", " "}


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

    def __init__(self, regions: dict[str, Region] | None = None) -> None:
        self.grid: list[list[int]] = [[codes_mod.BLANK] * COLS for _ in range(ROWS)]
        self.regions: dict[str, Region] = regions or {}

    @classmethod
    def from_file(cls, path: str | Path) -> Scene:
        raw = json.loads(Path(path).read_text())
        grid = raw["grid"] if isinstance(raw, dict) else raw
        return cls(regions=_parse_regions(grid))

    # -- placement -------------------------------------------------------------
    def _origin(self, region: str | None) -> tuple[int, int, int, int]:
        if region is None:
            return 0, 0, ROWS - 1, COLS - 1
        r = self.regions[region]
        return r.row0, r.col0, r.row1, r.col1

    def set(self, r: int, c: int, code: int) -> Scene:
        if not codes_mod.is_valid_code(code):
            raise ValueError(f"code {code} out of range 0-71")
        if 0 <= r < ROWS and 0 <= c < COLS:
            self.grid[r][c] = code
        return self

    def fill(self, code: int, region: str | None = None) -> Scene:
        r0, c0, r1, c1 = self._origin(region)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                self.set(r, c, code)
        return self

    def text(self, s: str, r: int = 0, c: int = 0, region: str | None = None) -> Scene:
        """Write ``s`` one character per cell, offset within ``region``."""
        r0, c0, r1, c1 = self._origin(region)
        for i, code in enumerate(codes_mod.text_to_codes(s)):
            col = c0 + c + i
            row = r0 + r
            if col > c1 or row > r1:
                break
            self.set(row, col, code)
        return self

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

    def stamp_centered(self, glyph: Glyph, on_code: int = codes_mod.WHITE, region: str | None = None) -> Scene:
        """Stamp a glyph centered within ``region`` (or the whole board)."""
        r0, c0, r1, c1 = self._origin(region)
        height, width = r1 - r0 + 1, c1 - c0 + 1
        r = max(0, (height - glyph.height) // 2)
        c = max(0, (width - glyph.width) // 2)
        return self.stamp(glyph, r, c, on_code, region)

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
