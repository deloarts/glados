"""
The column type of every piece quantity: NUMERIC(18, 6) in the database, a
float in Python. A value is rounded to six decimals on its way in, so SQLite
and Postgres store the same number and a sum of stored quantities never
drifts in the last binary digits. No config imports.
"""

from typing import Any

from sqlalchemy import Numeric
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

QUANTITY_DECIMALS = 6


class QuantityType(TypeDecorator[float]):
    impl = Numeric(18, QUANTITY_DECIMALS, asdecimal=False)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> float | None:
        if value is None:
            return None
        return round(float(value), QUANTITY_DECIMALS)

    def process_result_value(self, value: Any, dialect: Dialect) -> float | None:
        if value is None:
            return None
        return float(value)
