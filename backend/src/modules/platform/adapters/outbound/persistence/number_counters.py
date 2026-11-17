"""
Draws the next number of a numbering template, such as "PON-{seq:05d}" or
"L{year}{seq:04d}", from a counter row per number family and rendered
prefix (number_counter_table).

The draw adds one to the counter and returns it, so two creations never
compute the same number, and the counter's row lock keeps the next one
waiting until the drawing transaction ends; a rolled back creation leaves
its number to the next. The first draw of a prefix starts the counter
after the highest number already stored under that prefix, compared by
length and then by value, so "L20261000" counts after "L2026999" and a
number already stored without a draw is never drawn again. Stored
numbers whose rest after the prefix is not all digits are ignored there.
A date in the prefix is the tenant's day, in the default timezone of the
general settings, so a lot created just after midnight in Vienna carries
the new day, month or year.

A number is drawn only after every lifecycle row lock the transaction
takes (lifecycle_lock_plan.py): the counter row is a lock outside the
lifecycle lock order, and a transaction that held it while waiting for a
lifecycle row could close a cycle with one that holds that row and then
draws.
"""

import uuid
from datetime import date
from enum import StrEnum
from typing import Any
from typing import cast

from sqlalchemy import Table
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.like_escape import escape_like
from src.modules.platform.adapters.outbound.persistence.models.number_counter_model import (
    NumberCounterOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.tenant_zone import read_tenant_zone
from src.modules.platform.domain.services.numbering_format import render_prefix
from src.shared_kernel.domain.services.clock import now_utc

_COUNTER = cast(Table, NumberCounterOrmModel.__table__)


class NumberFamily(StrEnum):
    """The kinds of numbers that draw from their own counters. A prefix two
    families share still counts separately for each."""

    ORDER = "order"
    LOT = "lot"
    PRODUCTION_ORDER = "production_order"
    PART = "part"
    CALCULATION = "calculation"
    CHECKLIST = "checklist"
    SEQUENCE = "sequence"
    QUOTE_REQUEST = "quote_request"
    MEETING = "meeting"


async def highest_stored_sequence(db: AsyncSession, column: Any, prefix: str) -> int:
    """The sequence of the highest number stored in `column` under `prefix`,
    by length and then by value, among the numbers whose rest after the
    prefix is all digits; 0 when there is none."""
    numbers = await db.stream_scalars(
        select(column)
        .where(column.like(f"{escape_like(prefix)}%", escape="\\"))
        .order_by(desc(func.length(column)), desc(column))
    )
    async for number in numbers:
        rest = str(number)[len(prefix) :]
        if rest.isdigit():
            await numbers.close()
            return int(rest)
    return 0


def _insert(db: AsyncSession) -> Any:
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    return (postgresql if dialect == "postgresql" else sqlite).insert(_COUNTER)


async def draw_sequence(db: AsyncSession, family: NumberFamily, prefix: str, *, column: Any) -> int:
    """Adds one to the counter of (family, prefix) and returns it, starting
    the counter after the highest number stored in `column` under the
    prefix on its first draw. A concurrent first draw that creates the
    counter meanwhile is counted on, not overwritten."""
    key = (_COUNTER.c.family == family.value) & (_COUNTER.c.prefix == prefix)
    drawn = await db.scalar(
        update(_COUNTER)
        .where(key)
        .values(last_value=_COUNTER.c.last_value + 1)
        .returning(_COUNTER.c.last_value)
    )
    if drawn is not None:
        return int(drawn)
    start = await highest_stored_sequence(db, column, prefix) + 1
    statement = _insert(db).values(
        family=family.value, prefix=prefix, last_value=start, public_id=uuid.uuid4()
    )
    drawn = await db.scalar(
        statement.on_conflict_do_update(
            index_elements=[_COUNTER.c.family, _COUNTER.c.prefix],
            set_={"last_value": _COUNTER.c.last_value + 1},
        ).returning(_COUNTER.c.last_value)
    )
    return int(drawn)


async def tenant_today(db: AsyncSession) -> date:
    """Today in the tenant's default timezone, UTC when the general
    settings name none or an unknown one."""
    return now_utc().astimezone(await read_tenant_zone(db)).date()


async def draw_number(
    db: AsyncSession,
    family: NumberFamily,
    template: str,
    *,
    column: Any,
    today: date | None = None,
) -> str:
    """The next number of `template` for `family`, rendered for `today`, the
    tenant's day unless given, drawn per the module docstring."""
    day = today if today is not None else await tenant_today(db)
    prefix, width = render_prefix(template, today=day)
    sequence = await draw_sequence(db, family, prefix, column=column)
    return f"{prefix}{str(sequence).zfill(width)}"
