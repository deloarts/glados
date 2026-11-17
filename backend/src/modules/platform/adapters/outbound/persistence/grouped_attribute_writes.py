"""
Writes new column values onto many loaded ORM rows with a fixed number of
UPDATE round trips. The unit of work batches a flush's UPDATEs into one
executemany only while consecutive rows (in primary key order) change the
same set of columns, so rows that alternate between two column sets would
cost one statement each. Grouping the rows by the columns that actually
change and writing once per group keeps the count at one executemany per
distinct column set, however many rows there are.

Rows of a model without a version column stay ORM attribute changes, so
live row-sync (change_tracking, which inspects the flushed ORM objects in
after_flush and accumulates across flushes until commit) sees every changed
row. Rows of a versioned model cannot go through the flush that way: the
unit of work issues one UPDATE per versioned row, because it checks each
row's version. Those rows are written with one Core executemany per group
instead, which sets the new values and the next version by hand, records
each row for live sync and leaves the loaded objects holding what was
written. That skips the version check, so the caller must hold the rows'
locks, which keep them at the version it read. A row whose values are
already current is never touched.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from typing import Any
from typing import cast

from sqlalchemy import ColumnElement
from sqlalchemy import Table
from sqlalchemy import bindparam
from sqlalchemy import inspect
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper
from sqlalchemy.orm.attributes import set_committed_value

from src.modules.platform.adapters.outbound.persistence.change_tracking import record_update
from src.modules.platform.adapters.outbound.persistence.models.base import Base


async def flush_grouped_attribute_writes(
    db: AsyncSession, writes: Iterable[tuple[Base, Mapping[str, Any]]]
) -> None:
    """Applies each (row, {attribute: value}) pair, once per distinct set of
    changed attributes. The rows must have been loaded with their current
    database values (populate_existing), since an attribute only counts as
    changed when it differs from what the row holds, and rows of a versioned
    model must be locked by the caller; see the module docstring."""
    groups: dict[tuple[type[Base], tuple[str, ...]], list[tuple[Base, Mapping[str, Any]]]] = {}
    for row, values in writes:
        changed = tuple(name for name, value in values.items() if getattr(row, name) != value)
        if changed:
            groups.setdefault((type(row), changed), []).append((row, values))
    for (model, changed), members in groups.items():
        mapper: Mapper[Any] = inspect(model)
        version_column = mapper.version_id_col
        if version_column is None:
            for row, values in members:
                for name in changed:
                    setattr(row, name, values[name])
            await db.flush()
        else:
            await _write_versioned(db, mapper, version_column, changed, members)


async def _write_versioned(
    db: AsyncSession,
    mapper: Mapper[Any],
    version_column: ColumnElement[Any],
    changed: tuple[str, ...],
    members: list[tuple[Base, Mapping[str, Any]]],
) -> None:
    """One executemany for rows of one versioned model that change the same
    attributes, with the version incremented by hand."""
    version_key = mapper.get_property_by_column(version_column).key
    (primary_key,) = mapper.primary_key
    pk_key = mapper.get_property_by_column(primary_key).key
    columns = {name: mapper.columns[name] for name in (*changed, version_key)}
    statement = (
        update(cast(Table, mapper.local_table))
        .where(primary_key == bindparam("_pk", type_=primary_key.type))
        .values(
            {column: bindparam(f"_{name}", type_=column.type) for name, column in columns.items()}
        )
    )
    params = [
        {
            "_pk": getattr(row, pk_key),
            **{f"_{name}": values[name] for name in changed},
            f"_{version_key}": getattr(row, version_key) + 1,
        }
        for row, values in members
    ]
    await db.execute(statement, params)
    for row, values in members:
        for name in changed:
            set_committed_value(row, name, values[name])
        set_committed_value(row, version_key, getattr(row, version_key) + 1)
        record_update(db.sync_session, row)
