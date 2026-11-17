"""
Tracks whether an entity's data originates from web input or from the
CAD/PDM system. Flow between the two is one-way, WEB to CAD, per
docs/FIELD_OWNERSHIP.md; this value determines which fields are read-only
in the web UI versus overwritten unconditionally on PDM ingest.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class DataSource(StrValueEnum):
    WEB = "WEB"
    CAD = "CAD"

    @classmethod
    def default(cls) -> "DataSource":
        return cls.WEB
