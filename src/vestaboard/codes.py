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

MIN_CODE = 0
MAX_CODE = 71

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
