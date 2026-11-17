"""
Shared SQL predicates over demand/allocation quantities, used by all three
demand repositories (bought-item, source-item, made-item), plus the bucket
filter and list ordering those repositories build the same way.

These exist because the stored demand `status` column is deliberately
coarse: the lifecycle derivation (domain/services/lifecycle/demand.py)
calls a demand ALLOCATED as soon as *any* quantity is covered and until
every covering line or lot is placed, so "covered 1 of 10" and "covered 10
of 10 on a pending line" are the same stored value. The
partially-allocated/fully-allocated distinction the UI shows is derived
from allocation quantities, and filtering on it therefore needs quantity
maths in SQL rather than a status comparison.
"""

from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import nulls_last
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped

from src.modules.platform.adapters.outbound.persistence.statements import order_term


def demand_not_fully_allocated(
    *,
    demand_id: Mapped[int],
    demand_quantity: Mapped[float],
    demand_status: Mapped[str],
    allocation_demand_item_id: Mapped[int],
    allocation_quantity: Mapped[float],
    terminal_statuses: Sequence[str],
) -> ColumnElement[bool]:
    """Demands that still have quantity left to allocate, i.e. the rows the
    Manage Orders / Manage Lots panels can actually act on, everything the
    UI renders as "open" or "partially allocated", plus partially-ordered
    rows whose remaining quantity nobody has covered yet.

    covered = SUM(allocation.quantity) over *all* the demand's allocations.
    Stock-sourced allocations are intentionally included: they count toward
    coverage in compute_coverage_totals (as `fulfilled_from_stock`) exactly
    like order- and lot-sourced ones do, and the frontend's
    computeDisplayStatus sums the two the same way. Which non-stock source
    an allocation carries is irrelevant here, bought/source-item
    allocations point at order items and made-item allocations at
    production lots, but both contribute their full quantity to coverage.

    Terminal demands are excluded outright, a canceled demand can sit
    below full coverage forever and is not actionable.
    """
    covered = (
        select(func.coalesce(func.sum(allocation_quantity), 0.0))
        .where(allocation_demand_item_id == demand_id)
        .scalar_subquery()
    )
    return and_(
        demand_status.notin_(terminal_statuses),
        covered < demand_quantity,
    )


def demand_todo_candidate(
    *,
    demand_status: Mapped[str],
    desired_delivery_date: Mapped[date | None],
    open_status: str,
    horizon: date,
) -> ColumnElement[bool]:
    """The demands the Todo page can turn into an "order this" task: an
    open one without a desired date or wanted by `horizon`. The page decides
    the bucket, so this only keeps out the rows that can never give a task."""
    return and_(
        demand_status == open_status,
        or_(desired_delivery_date.is_(None), desired_delivery_date <= horizon),
    )


async def demand_status_counts(db: AsyncSession, demand_status: Mapped[str]) -> dict[str, int]:
    """How many demands of one kind hold each stored status. Every demand
    names a project, so this counts the rows the unfiltered list returns."""
    rows = await db.execute(select(demand_status, func.count()).group_by(demand_status))
    return {status: count for status, count in rows.tuples()}


def bucket_clause(
    bucket_column: Mapped[int | None],
    bucket_ids: Sequence[int] | None,
    include_unbucketed: bool | None,
) -> ColumnElement[bool]:
    """Demands in one of `bucket_ids`, or without a bucket when
    `include_unbucketed` is set. Buckets are display state only, and the
    caller only builds this once it knows at least one of the two is given,
    matching the API contract."""
    conditions: list[ColumnElement[bool]] = []
    if bucket_ids:
        conditions.append(bucket_column.in_(bucket_ids))
    if include_unbucketed:
        conditions.append(bucket_column.is_(None))
    return or_(*conditions)


def demand_secondary_sort(
    order_by: str | None,
    order_dir: str | None,
    sort_columns: Mapping[str, Any],
    default_column: Mapped[Any],
) -> ColumnElement[Any]:
    """The demand list's ordering after its fixed leading key: the requested
    column in the requested direction, or `default_column` descending, the
    newest demands first, when no known column is requested. The outer-joined
    bucket name sorts its NULLs, the unbucketed demands, last in both
    directions, per the API contract."""
    if not order_by or order_by not in sort_columns:
        return desc(default_column)
    secondary = order_term(sort_columns[order_by], order_dir, default="desc")
    if order_by == "bucket_name":
        return nulls_last(secondary)
    return secondary
