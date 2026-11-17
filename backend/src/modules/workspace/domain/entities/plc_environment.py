"""
A PLC environment, such as Siemens TIA Portal: how the PLC variables of a
machine are named and exported for it. It holds a prefix per signal type,
the longest tag the environment accepts, the character conversion applied
when a tag is built, the tag tables and the columns of the export. A
product picks one; a product without one uses the default environment.

The list is maintained by the PLC engineer among the device resources. An
environment in use is archived, never deleted, so products keep resolving
it.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.workspace.domain.value_objects.plc_environment_settings import CharConversion
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumn
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PlcEnvironment(Entity):
    created: datetime
    changed: datetime
    changes: list[str]

    name: str
    is_default: bool
    # Prefix key (PREFIX_KEYS) to prefix, such as "di" to "di_".
    prefixes: dict[str, str]
    max_tag_length: int
    conversions: list[CharConversion]
    tag_table: str
    # The tag table of safety signals; None keeps them in `tag_table`.
    safety_tag_table: str | None
    export_sheet: str
    export_columns: list[ExportColumn]

    # None for the environment the installation ships with.
    creator_id: int | None = None
    changed_by_id: int | None = None
    archived: bool = False
