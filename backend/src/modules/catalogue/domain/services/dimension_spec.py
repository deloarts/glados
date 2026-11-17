"""
Duplicate-detection canonicalization for SourceItem.dimension. Mirrors the
shapes the frontend's SourceItemDimensionInput.vue produces (box/hollow-box/
rod/hollow-rod/custom), but widens the separator/prefix character classes
so text typed by hand with an ASCII "x" or lowercase "ø" still canonicalizes
the same way as freshly-formatted "×"/"Ø" strings. Only a box's three
numbers are permutation-equivalent (100 × 200 × 20 ≡ 200 × 100 × 20); a
rod's diameter and length, or a hollow box's four numbers, are not
interchangeable, so those shapes only get whitespace/number normalization.

Kept in sync with the frontend mirror at
frontend/src/features/source-items/utils/dimensionSpec.ts. The two
must agree byte-for-byte or the frontend's duplicate warning and this
service's 409 will disagree.
"""

import re

_NUMBER = r"-?\d+(?:\.\d+)?"
_SEP = r"\s*[×xX*]\s*"
_DIA = "[Øø]"

_HOLLOW_ROD_RE = re.compile(rf"^{_DIA}({_NUMBER}){_SEP}({_NUMBER}){_SEP}({_NUMBER})$")
_ROD_RE = re.compile(rf"^{_DIA}({_NUMBER}){_SEP}({_NUMBER})$")
_HOLLOW_BOX_RE = re.compile(rf"^({_NUMBER}){_SEP}({_NUMBER}){_SEP}({_NUMBER}){_SEP}({_NUMBER})$")
_BOX_RE = re.compile(rf"^({_NUMBER}){_SEP}({_NUMBER}){_SEP}({_NUMBER})$")


def _normalize_number(raw: str) -> str:
    """String surgery rather than a float round-trip, so a huge or oddly
    precise value can't drift: "100.0" -> "100", "12.50" -> "12.5"."""
    if "." not in raw:
        return raw
    stripped = raw.rstrip("0")
    return stripped.rstrip(".") if stripped.endswith(".") else stripped


def canonicalize_dimension(dimension: str | None) -> str | None:
    if dimension is None:
        return None
    trimmed = " ".join(dimension.split())
    if trimmed == "":
        return None

    hollow_rod = _HOLLOW_ROD_RE.match(trimmed)
    if hollow_rod:
        a, b, c = (_normalize_number(g) for g in hollow_rod.groups())
        return f"Ø{a} × {b} × {c}"

    rod = _ROD_RE.match(trimmed)
    if rod:
        a, b = (_normalize_number(g) for g in rod.groups())
        return f"Ø{a} × {b}"

    hollow_box = _HOLLOW_BOX_RE.match(trimmed)
    if hollow_box:
        a, b, c, d = (_normalize_number(g) for g in hollow_box.groups())
        return f"{a} × {b} × {c} × {d}"

    box = _BOX_RE.match(trimmed)
    if box:
        numbers = sorted((_normalize_number(g) for g in box.groups()), key=float, reverse=True)
        return " × ".join(numbers)

    return trimmed
