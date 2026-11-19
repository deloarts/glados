"""
A column type for a short list of plain strings, stored as JSON text. It is
Text rather than JSON in the database so that the stored text keeps every
character as typed (`ensure_ascii=False`): a case-insensitive LIKE on the
column then finds a substring of any entry, umlauts included, on Postgres
and SQLite alike. No config imports.
"""

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class StringListType(TypeDecorator[list[str]]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return json.dumps([str(entry) for entry in value], ensure_ascii=False)

    def coerce_compared_value(self, op: Any, value: Any) -> Any:
        # A text compared with the column, such as a LIKE pattern, is bound
        # as plain text; only a list goes through process_bind_param.
        if isinstance(value, str):
            return Text()
        return self

    def process_result_value(self, value: Any, dialect: Dialect) -> list[str] | None:
        if value is None:
            return None
        loaded = json.loads(value) if value else []
        # A row written outside the application may hold anything; only a
        # list of strings is read back as entries.
        if not isinstance(loaded, list):
            return []
        return [str(entry) for entry in loaded]
