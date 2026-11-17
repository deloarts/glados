"""
The comparison form of a manufacturer order code. Catalogues, CAD files and
spreadsheets write the same code with or without separators (3RT2015-1BB41,
3RT20151BB41, 3rt2015 1bb41), so matching an item by its order code ignores
case, whitespace and the separators below. The stored value is never
changed; only comparisons use this form.
"""

ORDER_CODE_SEPARATORS = (" ", "-", ".", "/", "_")


def normalize_order_code(value: str | None) -> str:
    """Lower case, with whitespace and the separators removed."""
    text = "".join((value or "").split()).lower()
    for separator in ORDER_CODE_SEPARATORS:
        text = text.replace(separator, "")
    return text
