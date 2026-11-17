"""Localization language constants for UI and user communication (German
Austria and British English)."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class Language(StrValueEnum):
    deAT = "deAT"
    enGB = "enGB"

    @classmethod
    def default(cls) -> "Language":
        return cls.enGB
