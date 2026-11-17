"""
The smart filters of SqlAlchemyProductionLotRepository.get_multi, run
against the throwaway SQLite database: actionable_for in its source,
machines and orders modes, which surfaces only lots that still need a
decision, and the coverable_by_* filters, which keep the lots that a given
machine, pool or any pool could still take.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.production_lot_repository._helpers import _make_bare_lot
from tests.integration.production_lot_repository._helpers import _make_fabrication_method
from tests.integration.production_lot_repository._helpers import _make_internal_position_with_order
from tests.integration.production_lot_repository._helpers import _make_lot_with_position
from tests.integration.production_lot_repository._helpers import _make_open_demand


class TestActionableForSource:
    """actionable_for='source' is lot-level (mirrors
    lotSourceEligibility.ts's canSwitchMaterialSource): a lot without a
    linked demand, or whose linked demand is still 'open', is switchable;
    a lot with a further-progressed demand or in a terminal status is not."""

    async def test_lot_without_input_demand_is_actionable(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-1", LotStatus.DRAFT, None)

        repo = SqlAlchemyProductionLotRepository(db)
        _total, lots = await repo.get_multi(LotFilterDto(actionable_for="source"))

        assert lot_id in [lot.id for lot in lots]

    async def test_lot_with_open_demand_is_actionable(self, db, create_user):
        user = await create_user()
        project = await SqlAlchemyProjectRepository(db).save(
            Project(
                id=0, created=datetime.now(UTC), creator_id=user.id, project_number="P-SRC-OPEN"
            )
        )
        demand_id = await _make_open_demand(db, user.id, project.id, SourceItemDemandStatus.OPEN)
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-2", LotStatus.DRAFT, demand_id)

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="source"))

        assert lot_id in [lot.id for lot in lots]

    async def test_lot_with_ordered_demand_is_not_actionable(
        self, db, create_user, allow_lifecycle_drift
    ):
        # The demand statuses are written by hand for the filter under test,
        # without the allocations they derive from.
        user = await create_user()
        project = await SqlAlchemyProjectRepository(db).save(
            Project(
                id=0, created=datetime.now(UTC), creator_id=user.id, project_number="P-SRC-ORDERED"
            )
        )
        demand_id = await _make_open_demand(db, user.id, project.id, SourceItemDemandStatus.ORDERED)
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-3", LotStatus.DRAFT, demand_id)

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="source"))

        assert lot_id not in [lot.id for lot in lots]

    async def test_completed_lot_is_not_actionable(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-4", LotStatus.COMPLETED, None)

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="source"))

        assert lot_id not in [lot.id for lot in lots]

    async def test_canceled_lot_is_not_actionable(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-5", LotStatus.CANCELED, None)

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="source"))

        assert lot_id not in [lot.id for lot in lots]


async def _make_machine(
    db, creator_id: int, internal_name: str, fabrication_method_ids: list[int]
) -> ProductionMachine:
    saved = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=internal_name,
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=fabrication_method_ids,
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _make_pool(db, creator_id: int, name: str, machine_ids: list[int]) -> MachinePool:
    saved = await SqlAlchemyMachinePoolRepository(db).save(
        MachinePool(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            name=name,
            machine_ids=machine_ids,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


class TestActionableForMachines:
    """actionable_for='machines' is Manage Production's smart filter:
    only lots with a position still needing a machine decision should
    surface. A force-canceled or force-completed lot's still-unassigned
    position (the lot's cancel or force-complete leaves its kind
    untouched) is not actionable, and neither is an already-queued
    pure-manual position (its order's machine_id is null by design,
    permanently)."""

    async def test_unassigned_position_with_remaining_is_actionable(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-1")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-ACT-1", [method.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="machines"))

        assert lot_id in [lot.id for lot in lots]

    async def test_canceled_position_is_not_actionable(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-2")
        lot_id, position_id = await _make_lot_with_position(db, user.id, "LN-ACT-2", [method.id])
        lot_repo = SqlAlchemyProductionLotRepository(db)
        position = await lot_repo.get_position_by_id(position_id)
        assert position is not None
        position.status = LotPositionStatus.CANCELED
        await lot_repo.save_position(position)

        _, lots = await lot_repo.get_multi(LotFilterDto(actionable_for="machines"))

        assert lot_id not in [lot.id for lot in lots]

    async def test_force_completed_unassigned_position_is_not_actionable(self, db, create_user):
        """A force-completed lot's positions end COMPLETED, including one
        that was never ordered against at all, whose kind stays untouched.
        _position_remaining_expr only derives "remaining" from committed
        OrderItem/ProductionOrder quantities, so without the status check
        such a position would read as still having its full original
        quantity remaining forever after."""
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-6")
        lot_id, position_id = await _make_lot_with_position(db, user.id, "LN-ACT-6", [method.id])
        lot_repo = SqlAlchemyProductionLotRepository(db)
        position = await lot_repo.get_position_by_id(position_id)
        assert position is not None
        position.status = LotPositionStatus.COMPLETED
        position.quantity_completed = position.quantity
        await lot_repo.save_position(position)

        _, lots = await lot_repo.get_multi(LotFilterDto(actionable_for="machines"))

        assert lot_id not in [lot.id for lot in lots]

    async def test_internal_position_still_needing_a_machine_is_actionable(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-3")
        lot_id, _ = await _make_internal_position_with_order(
            db, user.id, "LN-ACT-3", [method.id], machine_id=None
        )

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="machines"))

        assert lot_id in [lot.id for lot in lots]

    async def test_already_resolved_internal_position_is_not_actionable(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-4")
        machine = await _make_machine(db, user.id, "Lathe ACT-4", [method.id])
        lot_id, _ = await _make_internal_position_with_order(
            db, user.id, "LN-ACT-4", [method.id], machine_id=machine.id
        )

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="machines"))

        assert lot_id not in [lot.id for lot in lots]

    async def test_manual_only_internal_position_is_not_actionable(self, db, create_user):
        """A pure-manual position's order is permanently machine-less by
        design (position_is_manual), not missing a machine decision, so
        _position_actionable_for_machines must not treat it as actionable
        just because machine_id IS NULL is true for it forever."""
        user = await create_user()
        manual_method = await _make_fabrication_method(
            db, user.id, "Cutting-ACT-5", requires_machine=False
        )
        lot_id, _ = await _make_internal_position_with_order(
            db, user.id, "LN-ACT-5", [manual_method.id], machine_id=None
        )

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(actionable_for="machines"))

        assert lot_id not in [lot.id for lot in lots]


class TestActionableForOrders:
    """actionable_for='orders' has the same force-cancel/force-complete gap
    as machines mode, in _actionable_lot_exists's own 'orders' predicate
    branch."""

    async def test_canceled_position_is_not_actionable(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-O1")
        lot_id, position_id = await _make_lot_with_position(db, user.id, "LN-ACT-O1", [method.id])
        lot_repo = SqlAlchemyProductionLotRepository(db)
        position = await lot_repo.get_position_by_id(position_id)
        assert position is not None
        position.status = LotPositionStatus.CANCELED
        await lot_repo.save_position(position)

        _, lots = await lot_repo.get_multi(LotFilterDto(actionable_for="orders"))

        assert lot_id not in [lot.id for lot in lots]

    async def test_force_completed_unassigned_position_is_not_actionable(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-ACT-O2")
        lot_id, position_id = await _make_lot_with_position(db, user.id, "LN-ACT-O2", [method.id])
        lot_repo = SqlAlchemyProductionLotRepository(db)
        position = await lot_repo.get_position_by_id(position_id)
        assert position is not None
        position.status = LotPositionStatus.COMPLETED
        position.quantity_completed = position.quantity
        await lot_repo.save_position(position)

        _, lots = await lot_repo.get_multi(LotFilterDto(actionable_for="orders"))

        assert lot_id not in [lot.id for lot in lots]


class TestCoverableByFilters:
    """coverable_by_machine_id / coverable_by_pool_id / coverable_by_any_pool:
    "which lots could still be routed to machine
    #X / pool #X / some pool", server-side rather than a client-side
    capability check per row."""

    async def test_covered_by_machine(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-A")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-1", [method.id])
        machine = await _make_machine(db, user.id, "Lathe A", [method.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_machine_id=machine.id))

        assert lot_id in [lot.id for lot in lots]

    async def test_not_covered_by_machine_missing_method(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-B")
        other_method = await _make_fabrication_method(db, user.id, "Milling-B")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-2", [method.id])
        machine = await _make_machine(db, user.id, "Mill B", [other_method.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_machine_id=machine.id))

        assert lot_id not in [lot.id for lot in lots]

    async def test_covered_by_pool_when_every_member_provides_the_method(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-C")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-3", [method.id])
        m1 = await _make_machine(db, user.id, "Lathe C1", [method.id])
        m2 = await _make_machine(db, user.id, "Lathe C2", [method.id])
        pool = await _make_pool(db, user.id, "Pool C", [m1.id, m2.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_pool_id=pool.id))

        assert lot_id in [lot.id for lot in lots]

    async def test_not_covered_by_pool_when_one_member_lacks_the_method(self, db, create_user):
        """Intersection-of-members semantics (mirrors
        assert_pool_capability_match): one member missing the method sinks
        the whole pool's coverage, even though another member has it."""
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-D")
        other_method = await _make_fabrication_method(db, user.id, "Milling-D")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-4", [method.id])
        m1 = await _make_machine(db, user.id, "Lathe D1", [method.id])
        m2 = await _make_machine(db, user.id, "Lathe D2", [other_method.id])
        pool = await _make_pool(db, user.id, "Pool D", [m1.id, m2.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_pool_id=pool.id))

        assert lot_id not in [lot.id for lot in lots]

    async def test_empty_pool_never_covers(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-E")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-5", [method.id])
        pool = await _make_pool(db, user.id, "Pool E", [])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_pool_id=pool.id))

        assert lot_id not in [lot.id for lot in lots]

    async def test_coverable_by_any_pool_true_when_at_least_one_pool_covers(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-F")
        other_method = await _make_fabrication_method(db, user.id, "Milling-F")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-6", [method.id])
        weak_machine = await _make_machine(db, user.id, "Mill F1", [other_method.id])
        strong_machine = await _make_machine(db, user.id, "Lathe F2", [method.id])
        await _make_pool(db, user.id, "Pool F weak", [weak_machine.id])
        await _make_pool(db, user.id, "Pool F strong", [strong_machine.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_any_pool=True))

        assert lot_id in [lot.id for lot in lots]

    async def test_coverable_by_any_pool_false_when_no_pool_covers(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-G")
        other_method = await _make_fabrication_method(db, user.id, "Milling-G")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-7", [method.id])
        weak_machine = await _make_machine(db, user.id, "Mill G1", [other_method.id])
        await _make_pool(db, user.id, "Pool G weak", [weak_machine.id])

        # a sibling lot that IS covered by Pool G weak (needs other_method,
        # which weak_machine provides): without this, a false negative on
        # the uncovered lot above could hide behind an equally-wrong empty
        # result. 2 lots, filter must return exactly the 1 covered one, not 0.
        covered_sibling_id, _ = await _make_lot_with_position(
            db, user.id, "LN-COV-7B", [other_method.id]
        )

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_any_pool=True))

        lot_ids = [lot.id for lot in lots]
        assert lot_id not in lot_ids
        assert covered_sibling_id in lot_ids

    async def test_coverable_by_any_pool_is_unaffected_by_unrelated_uncovered_lots(
        self, db, create_user
    ):
        """`_position_uncovered_by_pool`'s inner EXISTS must stay
        correlated to the current lot position two levels up (the
        'coverable_by_any_pool' nesting: lot -> some-pool-covers-position
        -> uncovered-step) through `.correlate(LotPositionOrmModel)`, or
        its scan runs over every lot position in the database instead of
        just the current lot's. An unrelated lot with a position no pool
        covers must not make an otherwise-covered lot disappear from the
        filter."""
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-K")
        other_method = await _make_fabrication_method(db, user.id, "Milling-K")

        covered_lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-K1", [method.id])
        covering_machine = await _make_machine(db, user.id, "Lathe K1", [method.id])
        await _make_pool(db, user.id, "Pool K covering", [covering_machine.id])

        # Unrelated lot: needs a method no pool anywhere provides.
        await _make_lot_with_position(db, user.id, "LN-COV-K2", [other_method.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_any_pool=True))

        assert covered_lot_id in [lot.id for lot in lots]

    async def test_coverable_by_pool_id_is_unaffected_by_unrelated_uncovered_lots(
        self, db, create_user
    ):
        """Same shape as the any_pool test above but for the pool_id
        branch, which already correlates correctly (pool_id there is a
        literal/single-level-correlated column, never nested inside
        another EXISTS). This pins that `.correlate()` does not regress it.
        Must already pass, before and after."""
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-L")
        other_method = await _make_fabrication_method(db, user.id, "Milling-L")

        covered_lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-L1", [method.id])
        covering_machine = await _make_machine(db, user.id, "Lathe L1", [method.id])
        pool = await _make_pool(db, user.id, "Pool L covering", [covering_machine.id])

        await _make_lot_with_position(db, user.id, "LN-COV-L2", [other_method.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_pool_id=pool.id))

        assert covered_lot_id in [lot.id for lot in lots]

    async def test_coverable_by_any_pool_ignores_deleted_pools(self, db, create_user):
        user = await create_user()
        method = await _make_fabrication_method(db, user.id, "Turning-H")
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-8", [method.id])
        machine = await _make_machine(db, user.id, "Lathe H", [method.id])
        pool = await _make_pool(db, user.id, "Pool H", [machine.id])
        await SqlAlchemyMachinePoolRepository(db).delete(pool)

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(coverable_by_any_pool=True))

        assert lot_id not in [lot.id for lot in lots]

    async def test_manual_only_position_covered_by_any_pool_but_not_a_specific_target(
        self, db, create_user
    ):
        """A pure-manual position has no machine-requiring step at all and
        is queued machine-less regardless of what's picked, so it's
        irrelevant to any *specific* machine/pool. It must NOT count as
        "covered" there, or a lot whose only open position is manual would
        satisfy coverable_by_machine_id/coverable_by_pool_id for literally
        every machine/pool id, even one that doesn't exist.
        coverable_by_any_pool has no specific target to be
        irrelevant to: it's the coarse "not a dead end" pre-filter shown
        before a target is picked, so it still counts there."""
        user = await create_user()
        manual_method = await _make_fabrication_method(
            db, user.id, "Gluing-I", requires_machine=False
        )
        lot_id, _ = await _make_lot_with_position(db, user.id, "LN-COV-9", [manual_method.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, by_machine = await repo.get_multi(LotFilterDto(coverable_by_machine_id=999_999))
        _, by_pool = await repo.get_multi(LotFilterDto(coverable_by_pool_id=999_999))
        _, by_any_pool = await repo.get_multi(LotFilterDto(coverable_by_any_pool=True))

        assert lot_id not in [lot.id for lot in by_machine]
        assert lot_id not in [lot.id for lot in by_pool]
        assert lot_id in [lot.id for lot in by_any_pool]

    async def test_lot_with_real_and_manual_positions_not_coverable_by_unrelated_machine(
        self, db, create_user
    ):
        """A lot with a real machine-requiring position (turning) plus a
        separate, unrelated manual position (bluing) must not show up
        under coverable_by_pool_id for a pool that provides neither
        method. The manual position's own "always covered" would
        otherwise trivially satisfy the lot-level EXISTS, masking that the
        pool the user actually picked has nothing to do with this lot."""
        user = await create_user()
        turning = await _make_fabrication_method(db, user.id, "Turning-COV-11")
        manual_method = await _make_fabrication_method(
            db, user.id, "Bluing-COV-11", requires_machine=False
        )
        lot_id, position_id = await _make_lot_with_position(db, user.id, "LN-COV-11", [turning.id])
        lot_repo = SqlAlchemyProductionLotRepository(db)
        await lot_repo.save_position(
            LotPosition(
                id=0,
                created=datetime.now(UTC),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.UNASSIGNED,
                status=LotPositionStatus.PENDING,
                quantity=1.0,
                quantity_completed=0.0,
                note=None,
                creator_id=user.id,
                lot_id=lot_id,
            )
        )
        second_position = next(
            p for p in await lot_repo.get_positions(lot_id) if p.id != position_id
        )
        await lot_repo.save_step(
            LotStep(
                id=0,
                created=datetime.now(UTC),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=2,  # lot_step_table's UNIQUE is (lot_id, sequence), not per-position
                creator_id=user.id,
                fabrication_method_id=manual_method.id,
                lot_id=lot_id,
                position_id=second_position.id,
                source_process_id=None,
            )
        )
        unrelated_pool_machine = await _make_fabrication_method(db, user.id, "Milling-COV-11")
        unrelated_pool = await _make_pool(
            db,
            user.id,
            "Unrelated pool",
            [(await _make_machine(db, user.id, "Unrelated mill", [unrelated_pool_machine.id])).id],
        )

        _, lots = await lot_repo.get_multi(LotFilterDto(coverable_by_pool_id=unrelated_pool.id))

        assert lot_id not in [lot.id for lot in lots]

    async def test_mixed_method_position_requires_every_method_covered(self, db, create_user):
        user = await create_user()
        method_a = await _make_fabrication_method(db, user.id, "Turning-J")
        method_b = await _make_fabrication_method(db, user.id, "Milling-J")
        lot_id, _ = await _make_lot_with_position(
            db, user.id, "LN-COV-10", [method_a.id, method_b.id]
        )
        partial_machine = await _make_machine(db, user.id, "Partial J", [method_a.id])
        full_machine = await _make_machine(db, user.id, "Full J", [method_a.id, method_b.id])

        repo = SqlAlchemyProductionLotRepository(db)
        _, partial = await repo.get_multi(LotFilterDto(coverable_by_machine_id=partial_machine.id))
        _, full = await repo.get_multi(LotFilterDto(coverable_by_machine_id=full_machine.id))

        assert lot_id not in [lot.id for lot in partial]
        assert lot_id in [lot.id for lot in full]
