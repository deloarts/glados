"""
StrValueEnum is the base of the string enums that expose their allowed
values as a plain list, for request validation and for the option lists
the API hands to the frontend. It has no members itself, so subclasses
behave exactly like a `(str, Enum)` class.
"""

from enum import Enum


class StrValueEnum(str, Enum):
    """A string enum with a values() listing its member values in definition
    order."""

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
