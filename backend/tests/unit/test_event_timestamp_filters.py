"""
Range filters over the order/production event columns (`created`,
`ordered_date`, `delivery_date`, ...), which are timestamps, not dates.

The failure mode this guards against: a date-picker filter bound of
"through 2026-08-06" compared inclusively (`<=`) against a *timestamp*
column excludes every row from that day except one landing exactly at
midnight. Filters still speak calendar dates, so the repositories translate
them into half-open UTC intervals instead.
"""

import importlib
from collections.abc import AsyncIterator
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.adapters.outbound.persistence.tenant_zone import read_tenant_zone

# Import every model (same walk as alembic_imports.py) so Base.metadata is
# complete before create_all, a partial import leaves FKs unresolvable.
for _module_name in model_module_names():
    importlib.import_module(_module_name)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db
    await engine.dispose()


# ══════════════════════════════════════════════════════════════════════
# The bound helpers
# ══════════════════════════════════════════════════════════════════════


class TestDayBounds:
    def test_day_start_is_midnight_utc(self):
        assert day_start_utc(date(2026, 8, 6)) == datetime(2026, 8, 6, 0, 0, tzinfo=UTC)

    def test_day_after_is_next_midnight_utc(self):
        assert day_after_utc(date(2026, 8, 6)) == datetime(2026, 8, 7, 0, 0, tzinfo=UTC)

    def test_day_after_crosses_month_boundary(self):
        assert day_after_utc(date(2026, 8, 31)) == datetime(2026, 9, 1, 0, 0, tzinfo=UTC)

    def test_day_after_crosses_leap_day(self):
        assert day_after_utc(date(2028, 2, 28)) == datetime(2028, 2, 29, 0, 0, tzinfo=UTC)

    def test_a_late_evening_instant_falls_inside_its_own_day(self):
        """The whole point: 23:59 on day X is < the start of day X+1."""
        instant = datetime(2026, 8, 6, 23, 59, 59, tzinfo=UTC)
        assert day_start_utc(date(2026, 8, 6)) <= instant < day_after_utc(date(2026, 8, 6))

    def test_a_zone_reads_the_day_in_that_zone(self):
        """Vienna's 6 August runs from 22:00 UTC the day before (summer time)."""
        vienna = ZoneInfo("Europe/Vienna")
        assert day_start_utc(date(2026, 8, 6), vienna) == datetime(2026, 8, 5, 22, 0, tzinfo=UTC)
        assert day_after_utc(date(2026, 8, 6), vienna) == datetime(2026, 8, 6, 22, 0, tzinfo=UTC)

    def test_a_zone_follows_the_daylight_saving_switch(self):
        """25 October 2026 has 25 hours in Vienna, from 22:00 to 23:00 UTC."""
        vienna = ZoneInfo("Europe/Vienna")
        assert day_start_utc(date(2026, 10, 25), vienna) == datetime(
            2026, 10, 24, 22, 0, tzinfo=UTC
        )
        assert day_after_utc(date(2026, 10, 25), vienna) == datetime(
            2026, 10, 25, 23, 0, tzinfo=UTC
        )


# ══════════════════════════════════════════════════════════════════════
# Repository filtering
# ══════════════════════════════════════════════════════════════════════


async def _seed_order(
    session: AsyncSession, *, order_number: str, created: datetime
) -> OrderOrmModel:
    if not await session.scalar(select(UserOrmModel).limit(1)):
        session.add(
            UserOrmModel(
                id=1,
                username="tester",
                full_name="Tester",
                email="tester@example.com",
                created=datetime(2026, 1, 1, tzinfo=UTC),
                hashed_password="x",
                is_active=True,
                is_systemuser=True,
                permissions=[],
                language="enGB",
                date_format="iso",
                start_page="dashboard",
                theme_preset="Aura",
                theme_surface="glados",
                theme_primary="glados",
            )
        )
        session.add(
            SupplierOrmModel(
                id=1,
                name="Supplier",
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=datetime(2026, 1, 1, tzinfo=UTC),
                changes=[],
                creator_id=1,
            )
        )
        await session.flush()

    order = OrderOrmModel(
        order_number=order_number,
        created=created,
        changed=None,
        changes=[],
        status="draft",
        creator_id=1,
        supplier_id=1,
    )
    session.add(order)
    await session.commit()
    return order


class TestCreatedRangeFilterIncludesWholeDay:
    async def test_orders_created_later_in_the_day_survive_an_inclusive_to_bound(self, session):
        """An order created at 14:32 must still match `created_to=that same day`.

        With a `<=` comparison against the bare date, only a midnight-sharp
        row would match.
        """
        await _seed_order(
            session, order_number="ORD-MORNING", created=datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
        )
        await _seed_order(
            session, order_number="ORD-AFTERNOON", created=datetime(2026, 8, 6, 14, 32, tzinfo=UTC)
        )
        await _seed_order(
            session, order_number="ORD-LATE", created=datetime(2026, 8, 6, 23, 59, tzinfo=UTC)
        )

        repo = SqlAlchemyOrderRepository(session)
        total, orders = await repo.get_multi(
            OrderFilterDto(created_from=date(2026, 8, 6), created_to=date(2026, 8, 6))
        )

        assert total == 3
        assert {o.order_number for o in orders} == {"ORD-MORNING", "ORD-AFTERNOON", "ORD-LATE"}

    async def test_the_following_day_is_still_excluded(self, session):
        """Including all of the `_to` day must not spill into the next one."""
        await _seed_order(
            session, order_number="ORD-IN", created=datetime(2026, 8, 6, 23, 59, tzinfo=UTC)
        )
        await _seed_order(
            session, order_number="ORD-OUT", created=datetime(2026, 8, 7, 0, 0, tzinfo=UTC)
        )

        repo = SqlAlchemyOrderRepository(session)
        total, orders = await repo.get_multi(OrderFilterDto(created_to=date(2026, 8, 6)))

        assert total == 1
        assert orders[0].order_number == "ORD-IN"

    async def test_from_bound_includes_midnight_of_its_own_day(self, session):
        await _seed_order(
            session, order_number="ORD-BEFORE", created=datetime(2026, 8, 5, 23, 59, tzinfo=UTC)
        )
        await _seed_order(
            session, order_number="ORD-ON", created=datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
        )

        repo = SqlAlchemyOrderRepository(session)
        total, orders = await repo.get_multi(OrderFilterDto(created_from=date(2026, 8, 6)))

        assert total == 1
        assert orders[0].order_number == "ORD-ON"


# ══════════════════════════════════════════════════════════════════════
# The tenant's day
# ══════════════════════════════════════════════════════════════════════


async def _seed_tenant_zone(session: AsyncSession, name: str) -> None:
    session.add(AdminGeneralSettingsOrmModel(id=1, default_timezone=name))
    await session.commit()


class TestTenantZone:
    async def test_reads_the_default_timezone_of_the_general_settings(self, session):
        await _seed_tenant_zone(session, "Europe/Vienna")
        assert await read_tenant_zone(session) == ZoneInfo("Europe/Vienna")

    async def test_an_unknown_name_reads_as_utc(self, session):
        await _seed_tenant_zone(session, "Not/A_Zone")
        assert await read_tenant_zone(session) == ZoneInfo("UTC")

    async def test_a_missing_settings_row_reads_as_utc(self, session):
        assert await read_tenant_zone(session) == ZoneInfo("UTC")

    async def test_a_filter_with_a_day_reads_the_tenant_zone(self, session):
        await _seed_tenant_zone(session, "Europe/Vienna")
        zone = await date_filter_zone(session, None, date(2026, 11, 2))
        assert zone == ZoneInfo("Europe/Vienna")

    async def test_a_filter_without_a_day_runs_no_query(self):
        """No bound is built from the zone then, so UTC stands in unread: a
        query on the missing session would raise."""
        assert await date_filter_zone(cast(AsyncSession, None), None, None) is UTC


class TestDayFiltersReadTheTenantDay:
    """Vienna is UTC+1 on 2 November 2026, so 23:30 UTC on 1 November is
    already 00:30 on 2 November there. A user filtering by a day means the
    tenant's day, not UTC's."""

    async def test_an_instant_after_tenant_midnight_counts_on_the_new_day(self, session):
        await _seed_tenant_zone(session, "Europe/Vienna")
        await _seed_order(
            session, order_number="ORD-0030", created=datetime(2026, 11, 1, 23, 30, tzinfo=UTC)
        )
        repo = SqlAlchemyOrderRepository(session)

        total, orders = await repo.get_multi(
            OrderFilterDto(created_from=date(2026, 11, 2), created_to=date(2026, 11, 2))
        )
        assert total == 1
        assert orders[0].order_number == "ORD-0030"

        total, _ = await repo.get_multi(OrderFilterDto(created_to=date(2026, 11, 1)))
        assert total == 0

    async def test_an_instant_before_tenant_midnight_counts_on_the_old_day(self, session):
        await _seed_tenant_zone(session, "Europe/Vienna")
        await _seed_order(
            session, order_number="ORD-2330", created=datetime(2026, 11, 1, 22, 30, tzinfo=UTC)
        )
        repo = SqlAlchemyOrderRepository(session)

        total, _ = await repo.get_multi(OrderFilterDto(created_from=date(2026, 11, 2)))
        assert total == 0
        total, orders = await repo.get_multi(OrderFilterDto(created_to=date(2026, 11, 1)))
        assert total == 1
        assert orders[0].order_number == "ORD-2330"
