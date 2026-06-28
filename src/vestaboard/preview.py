"""Render a 6x22 board to the terminal so you can iterate without a real board.

Color cells become ANSI-colored blocks; letters/digits print as their character.
Each cell is two columns wide so the 22-wide board keeps a board-like aspect ratio.
"""

from __future__ import annotations

from . import COLS, ROWS
from . import codes as codes_mod

# Vestaboard color code -> ANSI 256-color background.
_COLOR_BG = {
    codes_mod.RED: 196,
    codes_mod.ORANGE: 208,
    codes_mod.YELLOW: 226,
    codes_mod.GREEN: 46,
    codes_mod.BLUE: 21,
    codes_mod.VIOLET: 93,
    codes_mod.WHITE: 231,
    codes_mod.BLACK: 16,
    codes_mod.FILLED: 231,
}


def _cell(code: int, color: bool) -> str:
    if code in _COLOR_BG:
        if color:
            return f"\033[48;5;{_COLOR_BG[code]}m  \033[0m"
        return "##"
    ch = codes_mod.CODE_TO_CHAR.get(code, "?")
    if ch == " ":
        return "  "
    return f"{ch} "


def render_preview(characters: list[list[int]], color: bool = True) -> str:
    """Return a printable picture of a 6x22 character-code grid."""
    if len(characters) != ROWS or any(len(row) != COLS for row in characters):
        raise ValueError("expected a 6x22 grid")
    border = "+" + "-" * (COLS * 2) + "+"
    out = [border]
    for row in characters:
        out.append("|" + "".join(_cell(code, color) for code in row) + "|")
    out.append(border)
    return "\n".join(out)
