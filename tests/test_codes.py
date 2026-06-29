from artistaboard import codes


def test_letters_digits_zero():
    assert codes.char_to_code("A") == 1
    assert codes.char_to_code("Z") == 26
    assert codes.char_to_code("1") == 27
    assert codes.char_to_code("9") == 35
    assert codes.char_to_code("0") == 36


def test_lowercase_is_uppercased():
    assert codes.char_to_code("a") == codes.char_to_code("A")


def test_blank_and_punctuation():
    assert codes.char_to_code(" ") == codes.BLANK
    assert codes.char_to_code(":") == 50
    assert codes.char_to_code("-") == 44


def test_text_to_codes_roundtrips_via_code_to_char():
    text = "L 5:12"
    out = codes.text_to_codes(text)
    assert "".join(codes.CODE_TO_CHAR[c] for c in out) == text


def test_colors_are_in_range():
    assert codes.GREEN == 66
    assert all(codes.is_valid_code(c) for c in codes.COLORS)
    assert not codes.is_valid_code(72)
    assert not codes.is_valid_code(-1)


def test_resolve_color_accepts_names_numbers_and_codes():
    assert codes.resolve_color("violet") == codes.VIOLET
    assert codes.resolve_color("purple") == codes.VIOLET  # alias
    assert codes.resolve_color("GREEN") == codes.GREEN  # case-insensitive
    assert codes.resolve_color(66) == codes.GREEN
    assert codes.resolve_color("66") == codes.GREEN  # numeric string


def test_resolve_color_rejects_garbage():
    import pytest

    for bad in ("mauve", 99, -1, True):
        with pytest.raises(ValueError):
            codes.resolve_color(bad)


def test_unknown_character_raises():
    import pytest

    with pytest.raises(ValueError):
        codes.char_to_code("~")
