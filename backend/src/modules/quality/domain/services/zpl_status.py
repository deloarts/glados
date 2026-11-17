"""
Pure parsing of a Zebra ZPL printer's `~HS` status reply into readable
lines. No I/O, the socket round trip lives in the printer gateway adapter;
this stays unit-testable with no printer present.
"""

import re

HEAD_DPI_DEFAULT = 300

# Printable text of a sensible length, as a Zebra identity reply is.
_IDENTITY = re.compile(r"[\x20-\x7e]{1,200}")

# The fields read from the first and second line of a ~HS reply, which a
# Zebra printer sends with 12 and 11 fields.
_LINE_ONE_FIELDS = 6
_LINE_TWO_FIELDS = 9

_PRINT_MODES = {
    "0": "rewind",
    "1": "peel-off",
    "2": "tear-off",
    "3": "cutter",
    "4": "applicator",
}


def describe_zpl_status(raw: str, *, head_dpi: int = HEAD_DPI_DEFAULT) -> list[str]:
    """Decode the three-line ``~HS`` reply into readable lines. A reply that
    is not of that shape is not shown, since whatever answered may not be a
    printer and its reply is not for the caller to read."""
    lines = [line.strip("\x02\x03\r\n") for line in raw.splitlines() if line.strip()]
    one = lines[0].split(",") if lines else []
    two = lines[1].split(",") if len(lines) > 1 else []
    if (
        len(one) < _LINE_ONE_FIELDS
        or len(two) < _LINE_TWO_FIELDS
        or not one[3].isdigit()
        or not two[8].isdigit()
    ):
        return [f"unexpected ~HS reply ({len(raw)} characters), not a ZPL printer?"]

    label_dots = int(one[3])
    return [
        f"paper out:      {'YES' if one[1] == '1' else 'no'}",
        f"paused:         {'YES' if one[2] == '1' else 'no'}",
        f"label length:   {label_dots} dots ({label_dots * 25.4 / head_dpi:.1f} mm)",
        f"buffer full:    {'YES' if one[5] == '1' else 'no'}",
        f"head up:        {'YES' if two[2] == '1' else 'no'}",
        f"ribbon out:     {'YES' if two[3] == '1' else 'no'}",
        f"media type:     {'thermal transfer' if two[4] == '1' else 'direct thermal'}",
        f"print mode:     {_PRINT_MODES.get(two[5], 'unknown')}",
        f"labels queued:  {int(two[8])}",
    ]


def describe_zpl_identity(raw: str) -> str:
    """Decode the ``~HI`` reply (``model,firmware,dots-per-mm,memory``). A
    reply that is not of that shape is not shown, since whatever answered
    may not be a printer."""
    text = raw.strip("\x02\x03\r\n")
    if not _IDENTITY.fullmatch(text):
        return f"unexpected ~HI reply ({len(raw)} characters), not a ZPL printer?"
    return text
