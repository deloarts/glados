"""
The column type of a stored percentage, such as a delivery tolerance:
NUMERIC(7, 3) in the database, a float in Python. A value is rounded to
three decimals on its way in, so SQLite and Postgres store the same number
and a value read back equals the one written. No config imports.
"""

from typing import Any

from sqlalchemy import Numeric
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

PERCENT_DECIMALS = 3


class PercentType(TypeDecorator[float]):
    impl = Numeric(7, PERCENT_DECIMALS, asdecimal=False)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> float | None:
        if value is None:
            return None
        return round(float(value), PERCENT_DECIMALS)

    def process_result_value(self, value: Any, dialect: Dialect) -> float | None:
        if value is None:
            return None
        return float(value)
