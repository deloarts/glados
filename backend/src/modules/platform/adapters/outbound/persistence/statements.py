"""
Small helpers for SQLAlchemy 2.0 `select()` statements that keep the exact
semantics of SQLAlchemy's legacy `Query` methods. `Query.count()` wraps
the query in a subquery and counts its rows, which is what `count_rows`
does too, so joins and DISTINCT count the same way.

The other helpers spell out statements that almost every repository
writes: one row by primary key, the rows of an id list, a sort term whose
direction comes from a filter, and a counted page of a filtered statement.
They build the same SQL the hand-written forms did, so a repository can use
them without changing what it sends to the database.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from typing import Any
from typing import Literal
from typing import TypeVar

from sqlalchemy import Select
from sqlalchemy import UnaryExpression
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.pagination import clamp_page

RowT = TypeVar("RowT")


async def count_rows(db: AsyncSession, stmt: Select[Any]) -> int:
    """Number of rows `stmt` returns, ignoring any ORDER BY, LIMIT or OFFSET
    the caller has not applied yet."""
    count = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return count or 0


def order_term(
    column: Any, order_dir: str | None, *, default: Literal["asc", "desc"]
) -> UnaryExpression[Any]:
    """`column` sorted in the `default` direction unless `order_dir` names
    the other one exactly. Any other value, None included, keeps the
    default, which is how each list query has always treated an unknown
    direction."""
    if default == "asc":
        return desc(column) if order_dir == "desc" else asc(column)
    return asc(column) if order_dir == "asc" else desc(column)


async def fetch_page(
    db: AsyncSession,
    stmt: Select[tuple[RowT]],
    skip: int | None,
    limit: int | None,
    *order_by: Any,
    options: Iterable[ORMOption] = (),
    min_limit: int | None = None,
) -> tuple[int, Sequence[RowT]]:
    """The total row count of `stmt` and one page of its rows.

    The count runs on `stmt` as given, through count_rows. The page adds
    the loader `options`, the `order_by` terms after any ordering `stmt`
    already carries, and the offset and limit that clamp_page derives from
    the raw `skip`, `limit` and `min_limit`."""
    total = await count_rows(db, stmt)
    safe_skip, safe_limit = clamp_page(skip, limit, min_limit=min_limit)
    page = stmt.options(*options).order_by(*order_by).offset(safe_skip).limit(safe_limit)
    return total, (await db.scalars(page)).all()


def by_id(
    model: type[RowT],
    id: int,
    *options: ORMOption,
    for_update: bool = False,
    refresh: bool = False,
) -> Select[tuple[RowT]]:
    """The row of `model` with primary key `id`, with the loader `options`.

    `for_update` locks the row (FOR NO KEY UPDATE, ignored by SQLite), the
    lock mode of the lifecycle row locks (repositories/_lifecycle_rows.py), and
    `refresh` sets populate_existing, so an instance already in the session
    is overwritten with the database state and gets the options applied.
    The caller adds `.limit(1)` where its query always had one."""
    stmt = select(model).where(_id_column(model) == id).options(*options)
    if for_update:
        stmt = stmt.with_for_update(key_share=True)
    if refresh:
        stmt = stmt.execution_options(populate_existing=True)
    return stmt


async def lock_row(db: AsyncSession, model: type[Any], id: int) -> None:
    """Locks the row of `model` with primary key `id` until the transaction
    ends, without loading it (FOR NO KEY UPDATE, ignored by SQLite). An edit
    takes it before it reads the row, so the edit version it checks is the
    one it overwrites."""
    column = _id_column(model)
    await db.execute(select(column).where(column == id).with_for_update(key_share=True))


async def load_by_ids(db: AsyncSession, model: type[RowT], ids: Iterable[int]) -> list[RowT]:
    """The rows of `model` whose primary key is in `ids`, in no particular
    order, as a list a relationship collection can be assigned from."""
    return list((await db.scalars(select(model).where(_id_column(model).in_(ids)))).all())


def _id_column(model: type[Any]) -> Any:
    """The mapped `id` column. The declarative base declares no `id`, every
    model does, so the attribute is read through Any."""
    return model.id
