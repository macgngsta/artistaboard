"""Vestaboard character codes and text <-> code conversion.

Reference: https://docs.vestaboard.com/docs/characterCodes
"""

from __future__ import annotations

BLANK = 0

# Colors.
RED = 63
ORANGE = 64
YELLOW = 65
GREEN = 66
BLUE = 67
VIOLET = 68
WHITE = 69
BLACK = 70
FILLED = 71

COLORS = frozenset({RED, ORANGE, YELLOW, GREEN, BLUE, VIOLET, WHITE, BLACK, FILLED})

# Human-readable color names -> code, so configs can say "violet" instead of 68.
NAME_TO_CODE: dict[str, int] = {
    "blank": BLANK,
    "red": RED,
    "orange": ORANGE,
    "yellow": YELLOW,
    "green": GREEN,
    "blue": BLUE,
    "violet": VIOLET,
    "purple": VIOLET,
    "white": WHITE,
    "black": BLACK,
    "filled": FILLED,
}
CODE_TO_NAME: dict[int, str] = {
    RED: "red",
    ORANGE: "orange",
    YELLOW: "yellow",
    GREEN: "green",
    BLUE: "blue",
    VIOLET: "violet",
    WHITE: "white",
    BLACK: "black",
    FILLED: "filled",
}

MIN_CODE = 0
MAX_CODE = 71


def resolve_color(value: int | str) -> int:
    """Resolve a color given as a code (``68``), numeric string (``"68"``), or
    name (``"violet"``/``"purple"``) to its Vestaboard code."""
    if isinstance(value, bool):
        raise ValueError(f"invalid color {value!r}")
    if isinstance(value, int):
        if is_valid_code(value):
            return value
        raise ValueError(f"color code {value} out of range 0-71")
    s = str(value).strip().lower()
    if s in NAME_TO_CODE:
        return NAME_TO_CODE[s]
    if s.lstrip("-").isdigit():
        return resolve_color(int(s))
    raise ValueError(f"unknown color {value!r}; use a name {sorted(NAME_TO_CODE)} or a code 0-71")


# Punctuation -> code. Codes 37-60 per the Vestaboard reference.
_PUNCTUATION: dict[str, int] = {
    "!": 37,
    "@": 38,
    "#": 39,
    "$": 40,
    "(": 41,
    ")": 42,
    "-": 44,
    "+": 46,
    "&": 47,
    "=": 48,
    ";": 49,
    ":": 50,
    "'": 52,
    '"': 53,
    "%": 54,
    ",": 55,
    ".": 56,
    "/": 59,
    "?": 60,
    "°": 62,
}

# Build the full character -> code map.
CHAR_TO_CODE: dict[str, int] = {" ": BLANK}
for _i, _ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=1):
    CHAR_TO_CODE[_ch] = _i
for _i, _ch in enumerate("123456789", start=27):
    CHAR_TO_CODE[_ch] = _i
CHAR_TO_CODE["0"] = 36
CHAR_TO_CODE.update(_PUNCTUATION)

CODE_TO_CHAR: dict[int, str] = {code: ch for ch, code in CHAR_TO_CODE.items()}


def char_to_code(ch: str) -> int:
    """Map a single character to its Vestaboard code (uppercasing letters)."""
    if len(ch) != 1:
        raise ValueError(f"expected a single character, got {ch!r}")
    upper = ch.upper()
    try:
        return CHAR_TO_CODE[upper]
    except KeyError as exc:
        raise ValueError(f"no Vestaboard code for character {ch!r}") from exc


def text_to_codes(text: str) -> list[int]:
    """Map a string to a list of Vestaboard codes."""
    return [char_to_code(ch) for ch in text]


def is_valid_code(code: int) -> bool:
    return MIN_CODE <= code <= MAX_CODE
