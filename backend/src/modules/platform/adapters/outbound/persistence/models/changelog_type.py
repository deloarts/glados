"""
The column type of every entity changelog: a JSON list of change records
(value_objects/change_entry.py) in the database, a list of ChangeEntry lines
in Python. A plain string, as a test may write, is stored as a record of its
text only. No config imports.
"""

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from src.shared_kernel.domain.value_objects.change_entry import ChangeEntry


class ChangelogType(TypeDecorator[list[str]]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> list[dict[str, Any]] | None:
        if value is None:
            return None
        # The line itself, not str(line): that would be a plain copy of the
        # text and lose the entry's parts.
        return [ChangeEntry.parse(line).to_record() for line in value]

    def process_result_value(self, value: Any, dialect: Dialect) -> list[str] | None:
        if value is None:
            return None
        return [ChangeEntry.from_record(record) for record in value]
