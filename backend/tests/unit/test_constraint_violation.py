"""
Unit tests for src/modules/platform/adapters/outbound/persistence/constraint_violation.py: an
engine with the translation attached raises an error that is both
SQLAlchemy's IntegrityError and the port-level ConstraintViolationError, at
flush and at commit, while other database errors pass through unchanged.
"""

import pytest
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import insert
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    register_constraint_violation_translation,
)
from src.modules.platform.ports.outbound.unit_of_work_port import ConstraintViolationError

_metadata = MetaData()
_lots = Table(
    "lot_table",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("lot_number", String, unique=True),
)


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    register_constraint_violation_translation(engine.sync_engine)
    async with engine.begin() as connection:
        await connection.run_sync(_metadata.create_all)
    return engine


async def test_a_unique_violation_is_both_integrity_error_and_port_error():
    engine = await _engine()
    try:
        async with engine.begin() as connection:
            await connection.execute(insert(_lots).values(lot_number="L-1"))
        with pytest.raises(ConstraintViolationError) as caught:
            async with engine.begin() as connection:
                await connection.execute(insert(_lots).values(lot_number="L-1"))
        assert isinstance(caught.value, IntegrityError)
        assert "lot_table.lot_number" in caught.value.constraint
        assert "UNIQUE constraint failed" in str(caught.value)
    finally:
        await engine.dispose()


async def test_other_database_errors_are_not_translated():
    engine = await _engine()
    try:
        with pytest.raises(OperationalError) as caught:
            async with engine.begin() as connection:
                await connection.execute(text("SELECT * FROM missing_table"))
        assert not isinstance(caught.value, ConstraintViolationError)
    finally:
        await engine.dispose()


def test_the_constraint_comes_from_the_driver_diagnostics_when_present():
    from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
        SqlConstraintViolationError,
    )

    class _Diag:
        constraint_name = "lot_table_lot_number_key"

    class _Orig(Exception):
        diag = _Diag()

    error = SqlConstraintViolationError(statement="INSERT", params={}, orig=_Orig("opaque"))
    assert error.constraint == "lot_table_lot_number_key"
