"""
Row locks and id pages shared by the repositories of the lifecycle
aggregates, internal to the persistence layer.

A lock selects the rows FOR NO KEY UPDATE in ascending id order, so two
transactions that lock overlapping sets of one table wait for each other
instead of deadlocking, and re-reads them (populate_existing), so the
session holds the committed row afterwards even where it had an older copy.
The lock never changes a key, so it leaves the key share lock of a foreign
key check free: a row that references a locked row can still be inserted or
updated, as when a transaction updates a lot's source demand a second time
and Postgres checks the demand's lot again. A FOR UPDATE lock would make that
write wait for the lot's writer, who may be waiting for the demand.
SQLite ignores FOR UPDATE, so the hermetic suite only sees the re-read. An
id page is the keyset read the lifecycle drift report walks a table with.
"""

from collections.abc import Collection

from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.modules.platform.adapters.outbound.persistence.models.base import Base


def lock_statement[M: Base](
    model: type[M], id_column: InstrumentedAttribute[int], ids: Collection[int]
) -> Select[tuple[M]]:
    """The rows with the given ids, locked and re-read in ascending id order."""
    return (
        select(model)
        .where(id_column.in_(sorted(set(ids))))
        .order_by(id_column)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )


async def lock_rows[M: Base](
    db: AsyncSession, model: type[M], id_column: InstrumentedAttribute[int], ids: Collection[int]
) -> None:
    """Takes the row locks of lock_statement. Every row is fetched, because a
    row lock is taken as the row is read. Nothing happens for no ids."""
    if not ids:
        return
    (await db.scalars(lock_statement(model, id_column, ids))).all()


def ids_after_statement(
    id_column: InstrumentedAttribute[int], after_id: int, limit: int
) -> Select[tuple[int]]:
    """Up to `limit` ids above `after_id`, ascending."""
    return select(id_column).where(id_column > after_id).order_by(id_column).limit(limit)


async def ids_after(
    db: AsyncSession, id_column: InstrumentedAttribute[int], after_id: int, limit: int
) -> list[int]:
    return list((await db.scalars(ids_after_statement(id_column, after_id, limit))).all())
