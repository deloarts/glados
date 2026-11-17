"""
Database-level guarantees of the three partial unique indexes on
ProductionOrderOrmModel.queue_sequence
(uq_production_order_queue_sequence_machine/_pool/_unassigned), scoped to
LIVE (non-terminal) orders only, mirroring next_queue_sequence's three
mutually exclusive scopes exactly (machine / pool-with-no-machine /
neither).

Rows are built by inserting ProductionOrderOrmModel directly (bypassing
both the use-case layer's guards, lock_queue_scope and the two-phase
rewrite, and the repository's save()), same rationale as
test_soft_delete_uniqueness.py: what's under test is a DB invariant, and
proving it holds even when every application-level safeguard is skipped is
the point. SQLite leaves foreign-key enforcement off by default
(conftest.py's _clean_tables docstring), so creator_id/lot_position_id
below don't need to reference real rows.

The reorder-under-load half (TestReorderUnderTheNewIndexes) instead drives
the real ReorderProductionOrders use case against the real
SqlAlchemyProductionOrderRepository, proving the two-phase write
(shift_queue_sequence then final values) survives a full,
non-adjacent shuffle and a scope with a fixed anchor mixed in. The
adjacent-swap case alone (unit + HTTP, both pinned pre-existing) doesn't
exercise either.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.use_cases.production_order.reorder_production_orders import (
    ReorderProductionOrders,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.adapters.outbound.persistence.event_outbox import OutboxEventBus
from src.modules.platform.adapters.outbound.persistence.statements import count_rows
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.domain.value_objects.permission import Permission


def _order_row(
    row_id: int,
    *,
    machine_id: int | None = None,
    machine_pool_id: int | None = None,
    queue_sequence: int,
    status: str = ProductionOrderStatus.QUEUED.value,
) -> ProductionOrderOrmModel:
    """A minimal, directly-constructed ProductionOrderOrmModel row: every
    NOT NULL column gets a fixed placeholder value except the ones the
    caller is testing (id, machine_id, machine_pool_id, queue_sequence,
    status)."""
    return ProductionOrderOrmModel(
        id=row_id,
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        production_order_number=f"PO-UQ-{row_id}",
        status=status,
        priority="normal",
        pinned=False,
        queue_sequence=queue_sequence,
        quantity=1.0,
        quantity_completed=0.0,
        estimated_duration_minutes=0,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        planned_by_id=None,
        machine_id=machine_id,
        machine_pool_id=machine_pool_id,
        lot_position_id=1,
    )


@pytest.fixture
async def conn(db):
    """Session on the shared engine, with production_order_table emptied."""
    await db.execute(delete(ProductionOrderOrmModel))
    await db.commit()
    return db


class TestPartialUniqueIndexesExist:
    @pytest.mark.parametrize(
        "index",
        [
            "uq_production_order_queue_sequence_machine",
            "uq_production_order_queue_sequence_pool",
            "uq_production_order_queue_sequence_unassigned",
        ],
    )
    async def test_index_exists_and_is_partial(self, conn, index):
        row = (
            await conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"), {"n": index}
            )
        ).first()
        assert row is not None, f"{index} is missing - was the model/migration reverted?"
        assert "UNIQUE" in row[0].upper()
        assert "WHERE" in row[0].upper(), f"{index} is not partial"


class TestMachineScope:
    async def test_duplicate_live_queue_sequence_on_same_machine_is_rejected(self, conn):
        conn.add(_order_row(1, machine_id=1, queue_sequence=1))
        await conn.commit()

        conn.add(_order_row(2, machine_id=1, queue_sequence=1))
        with pytest.raises(IntegrityError):
            await conn.commit()
        await conn.rollback()

    async def test_distinct_queue_sequence_on_same_machine_is_allowed(self, conn):
        conn.add(_order_row(1, machine_id=1, queue_sequence=1))
        conn.add(_order_row(2, machine_id=1, queue_sequence=2))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2

    async def test_same_queue_sequence_on_different_machines_is_allowed(self, conn):
        conn.add(_order_row(1, machine_id=1, queue_sequence=1))
        conn.add(_order_row(2, machine_id=2, queue_sequence=1))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2


class TestPoolScope:
    async def test_duplicate_live_queue_sequence_in_same_pool_is_rejected(self, conn):
        conn.add(_order_row(1, machine_pool_id=10, queue_sequence=1))
        await conn.commit()

        conn.add(_order_row(2, machine_pool_id=10, queue_sequence=1))
        with pytest.raises(IntegrityError):
            await conn.commit()
        await conn.rollback()

    async def test_same_queue_sequence_in_different_pools_is_allowed(self, conn):
        conn.add(_order_row(1, machine_pool_id=10, queue_sequence=1))
        conn.add(_order_row(2, machine_pool_id=20, queue_sequence=1))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2

    async def test_pool_scope_is_independent_of_the_unassigned_scope(self, conn):
        """machine_id=None, machine_pool_id=10 and machine_id=None,
        machine_pool_id=None must not share a number space."""
        conn.add(_order_row(1, machine_pool_id=10, queue_sequence=1))
        conn.add(_order_row(2, machine_pool_id=None, queue_sequence=1))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2


class TestUnassignedScope:
    async def test_duplicate_live_queue_sequence_with_no_machine_or_pool_is_rejected(self, conn):
        conn.add(_order_row(1, queue_sequence=1))
        await conn.commit()

        conn.add(_order_row(2, queue_sequence=1))
        with pytest.raises(IntegrityError):
            await conn.commit()
        await conn.rollback()

    async def test_distinct_queue_sequence_with_no_machine_or_pool_is_allowed(self, conn):
        conn.add(_order_row(1, queue_sequence=1))
        conn.add(_order_row(2, queue_sequence=2))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2


class TestTerminalOrdersAreExempt:
    """The index is partial on status NOT IN ('completed', 'canceled');
    a terminal order's queue_sequence is never cleared by any status
    transition, so
    historical duplicates among terminal rows must stay legal forever."""

    async def test_two_completed_orders_may_share_a_queue_sequence(self, conn):
        conn.add(
            _order_row(
                1, machine_id=1, queue_sequence=1, status=ProductionOrderStatus.COMPLETED.value
            )
        )
        conn.add(
            _order_row(
                2, machine_id=1, queue_sequence=1, status=ProductionOrderStatus.COMPLETED.value
            )
        )
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2

    async def test_a_canceled_order_may_share_a_queue_sequence_with_a_live_one(self, conn):
        conn.add(
            _order_row(
                1, machine_id=1, queue_sequence=1, status=ProductionOrderStatus.CANCELED.value
            )
        )
        conn.add(_order_row(2, machine_id=1, queue_sequence=1))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2

    async def test_a_live_order_still_cannot_share_a_queue_sequence_with_another_live_one(
        self, conn
    ):
        """Control case: the exemption is for terminal rows only, it must
        not have overshot into no uniqueness at all."""
        conn.add(_order_row(1, machine_id=1, queue_sequence=1))
        await conn.commit()

        conn.add(_order_row(2, machine_id=1, queue_sequence=1))
        with pytest.raises(IntegrityError):
            await conn.commit()
        await conn.rollback()

    async def test_completing_an_order_releases_its_slot_for_reuse(self, conn):
        """The index is enforced on UPDATE too: a live order transitioning
        to COMPLETED frees its (machine, queue_sequence) for a new live
        order to claim, without needing to change its own number."""
        conn.add(_order_row(1, machine_id=1, queue_sequence=1))
        await conn.commit()

        await conn.execute(
            update(ProductionOrderOrmModel)
            .filter_by(id=1)
            .values({"status": ProductionOrderStatus.COMPLETED.value})
        )
        await conn.commit()

        conn.add(_order_row(2, machine_id=1, queue_sequence=1))
        await conn.commit()

        assert await count_rows(conn, select(ProductionOrderOrmModel)) == 2


class TestReorderUnderTheNewIndexes:
    """Drives the real ReorderProductionOrders use case against the real
    SqlAlchemyProductionOrderRepository (not a fake). The two-phase write
    (shift_queue_sequence, then final values) has to survive the
    same immediate partial unique indexes TestMachineScope above just
    proved reject a bare duplicate."""

    def _reorder(self, db) -> ReorderProductionOrders:
        return ReorderProductionOrders(
            SqlAlchemyProductionOrderRepository(db),
            event_bus=OutboxEventBus(db),
            uow=SqlAlchemyUnitOfWork(db),
            lock_plan=LockPlan(sql_lifecycle_repositories(db)),
        )

    async def test_full_reversal_of_five_orders_succeeds(self, conn, create_user):
        user = await create_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        for i in range(1, 6):
            conn.add(_order_row(i, machine_id=1, queue_sequence=i))
        await conn.commit()

        use_case = self._reorder(conn)
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[5, 4, 3, 2, 1])
        results = await use_case.execute(user, machine_id=1, cmd=cmd)

        assert [r.id for r in results] == [5, 4, 3, 2, 1]
        by_id = {
            row.id: row.queue_sequence
            for row in (
                await conn.scalars(select(ProductionOrderOrmModel).filter_by(machine_id=1))
            ).all()
        }
        assert by_id == {5: 1, 4: 2, 3: 3, 2: 4, 1: 5}
        assert len(set(by_id.values())) == 5

    async def test_shuffle_around_a_pinned_anchor_does_not_collide(self, conn, create_user):
        """Live orders can have a pinned/IN_PROGRESS anchor interleaved
        among QUEUED ones, not confined to the front of the scope's number
        line. A reorder naming only the movable orders must not hand one of
        them the anchor's own number."""
        user = await create_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        conn.add(_order_row(1, machine_id=1, queue_sequence=1))
        conn.add(_order_row(2, machine_id=1, queue_sequence=2))
        anchor = _order_row(3, machine_id=1, queue_sequence=3)
        anchor.pinned = True
        conn.add(anchor)
        conn.add(_order_row(4, machine_id=1, queue_sequence=4))
        conn.add(_order_row(5, machine_id=1, queue_sequence=5))
        await conn.commit()

        use_case = self._reorder(conn)
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[5, 1, 4, 2])
        results = await use_case.execute(user, machine_id=1, cmd=cmd)

        assert [r.id for r in results] == [5, 1, 4, 2]
        by_id = {
            row.id: row.queue_sequence
            for row in (
                await conn.scalars(select(ProductionOrderOrmModel).filter_by(machine_id=1))
            ).all()
        }
        # The anchor's own number is untouched, and every touched order's
        # position relative to it is preserved: {1, 2} were below the
        # anchor's 3 and stay below; {4, 5} were above and stay above.
        assert by_id[3] == 3
        assert by_id[5] == 1
        assert by_id[1] == 2
        assert by_id[4] == 4
        assert by_id[2] == 5
        assert len(set(by_id.values())) == 5
