"""
Builds a product device's name from its four inputs: location, name,
driving medium letter and number, for example location "B01-W4-L", name
"Hubzylinder Einförderung", letter "P" and number 1.

The UTF-8 name keeps the input as typed, with runs of whitespace collapsed
and the parts joined by spaces: "B01-W4-L Hubzylinder Einförderung P1". The
ASCII name is what CAD file names and PLC tags are built from, so it holds
only letters, digits and underscores: umlauts and ß are transliterated,
other accents dropped, and every other character becomes an underscore,
runs of them collapsed into one: "B01_W4_L_Hubzylinder_Einfoerderung_P1".
A PLC environment may convert further when it builds its tags; the stored
ASCII name does not depend on one. The variants with the product number
put it in front with the same separator and are composed on read, because
a product number can change.

A character that cannot appear in a file name, or has no ASCII form after
transliteration, is rejected rather than silently replaced, so the ASCII
name is never a surprise. No I/O.
"""

import re
import unicodedata
from dataclasses import dataclass

from src.modules.workspace.domain.errors import ProductDeviceNameInvalidError

# Characters Windows refuses in file names.
FILE_NAME_ILLEGAL = frozenset('/\\:*?"<>|')

_TRANSLITERATION = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
    "ß": "ss",
    "ẞ": "SS",
}

# Runs of characters an identifier cannot hold, which become one underscore.
_NOT_IDENTIFIER = re.compile(r"[^A-Za-z0-9]+")

NAME_MAX_LENGTH = 120
LOCATION_MAX_LENGTH = 60


@dataclass(frozen=True)
class DeviceName:
    utf8: str
    ascii: str

    @property
    def ascii_key(self) -> str:
        """The ASCII name compared case-insensitively, as Windows file
        systems do."""
        return self.ascii.lower()


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def invalid_characters(text: str) -> list[str]:
    """The characters of `text` that a device name may not contain, each
    once, in order of appearance."""
    found: list[str] = []
    for char in text:
        bad = char in FILE_NAME_ILLEGAL or unicodedata.category(char).startswith("C")
        if not bad and not char.isascii():
            bad = not _transliterate_char(char).isascii()
        if bad and char not in found:
            found.append(char)
    return found


def _transliterate_char(char: str) -> str:
    if char in _TRANSLITERATION:
        return _TRANSLITERATION[char]
    decomposed = unicodedata.normalize("NFKD", char)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def to_ascii(text: str) -> str:
    """`text` transliterated to ASCII, with every run of characters other
    than letters and digits turned into one underscore and none left at
    either end. Assumes `invalid_characters(text)` is empty."""
    transliterated = "".join(_transliterate_char(c) for c in collapse_whitespace(text))
    return _NOT_IDENTIFIER.sub("_", transliterated).strip("_")


def clean_part(text: str, what: str, *, required: bool, max_length: int) -> str:
    """A name part as stored: whitespace collapsed, checked for length and
    for characters a device name may not contain."""
    value = collapse_whitespace(text)
    if required and not value:
        raise ProductDeviceNameInvalidError(f"The device {what} must not be empty.")
    if len(value) > max_length:
        raise ProductDeviceNameInvalidError(
            f"The device {what} is longer than {max_length} characters."
        )
    bad = invalid_characters(value)
    if bad:
        listed = " ".join(bad)
        raise ProductDeviceNameInvalidError(
            f"The device {what} contains characters a file name cannot hold: {listed}"
        )
    if required and not to_ascii(value):
        raise ProductDeviceNameInvalidError(
            f"The device {what} needs at least one letter or digit."
        )
    return value


def compose_device_name(location: str, name: str, letter: str, number: int) -> DeviceName:
    """The device's name without product number, from parts already
    cleaned by `clean_part`. Without a letter, for a device of a kind
    without driving medium, the first device of a name carries no number
    and the next ones carry theirs: "Taster Start", "Taster Start 2"."""
    counter = f"{letter}{number}" if letter else ("" if number == 1 else str(number))
    parts = [p for p in (location, name) if p]
    counters = [counter] if counter else []
    return DeviceName(
        utf8=" ".join([*parts, *counters]),
        ascii="_".join([*(a for a in (to_ascii(p) for p in parts) if a), *counters]),
    )


def group_key(location: str, name: str, letter: str) -> str:
    """What the device number counts within: location, name and letter,
    compared like the ASCII name, so "Einförderung" and "Einfoerderung"
    share their numbers."""
    return "_".join(a for a in (to_ascii(p) for p in (location, name, letter)) if a).lower()


def with_product_number(product_number: str, name: DeviceName) -> DeviceName:
    return DeviceName(
        utf8=f"{product_number} {name.utf8}",
        ascii=f"{to_ascii(product_number)}_{name.ascii}",
    )
