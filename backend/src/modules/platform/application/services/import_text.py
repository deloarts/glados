"""
Text helpers shared by the spreadsheet and portal imports of every module.
"""


def norm(value: str | None) -> str:
    """The form both sides of an exact lookup are compared in."""
    return (value or "").strip().lower()
