"""
Index rules for the ORM schema: every foreign key column is the leading
column of some index (Postgres does not create one on its own, and an
unindexed foreign key turns child lookups and parent deletes into table
scans), and no primary key carries a second index of its own.
"""

from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint

import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.modules.platform.adapters.outbound.persistence.models.base import Base


def _leading_columns(table: Table) -> set[str]:
    leading = {next(iter(index.columns)).name for index in table.indexes if index.columns}
    for constraint in table.constraints:
        if isinstance(constraint, PrimaryKeyConstraint | UniqueConstraint) and constraint.columns:
            leading.add(next(iter(constraint.columns)).name)
    return leading


def test_every_foreign_key_column_leads_an_index() -> None:
    unindexed = [
        f"{table.name}.{next(iter(fk.columns)).name}"
        for table in Base.metadata.tables.values()
        for fk in table.foreign_key_constraints
        if next(iter(fk.columns)).name not in _leading_columns(table)
    ]

    assert unindexed == [], f"add index=True to these foreign key columns: {sorted(unindexed)}"


def test_no_primary_key_has_a_redundant_index() -> None:
    redundant = [
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if [c.name for c in index.columns] == [c.name for c in table.primary_key.columns]
        and index.dialect_kwargs.get("postgresql_where") is None
    ]

    assert redundant == []
