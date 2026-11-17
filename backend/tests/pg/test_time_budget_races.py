"""
A race on the wider lock set of a time budget recompute, on a real
Postgres. A step edit in one lot locks the queued and paused orders of
every lot of the project before the time budget lock, so an order being
queued in another lot of the project, whose own recompute locks the same
orders, waits for the edit instead of snapshotting durations from budgets
the edit is about to change. Once both committed, every live order's
duration matches the budgets stored at the end.
"""

import dataclasses
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.fulfillment.adapters.inbound.api.deps import lots as lot_deps
from src.modules.fulfillment.adapters.inbound.api.deps import production as production_deps
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotStepCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from tests.integration.repository_reads._graph import make
from tests.pg._floor import Floor
from tests.pg._race import Gate
from tests.pg._race import outcomes
from tests.pg._race import request
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B


async def _position(floor: Floor, lot_id: int, sequence: int, kind: LotPositionKind) -> LotPosition:
    """A position of `lot_id` with one fabrication step drawing from the
    time budget, since it has no measured estimate."""
    repo = SqlAlchemyProductionLotRepository(floor.db)
    method = await floor.graph.fabrication_method()
    position = await repo.save_position(
        make(
            LotPosition,
            sequence=sequence,
            kind=kind,
            status=(
                LotPositionStatus.ORDERED_OR_QUEUED
                if kind is LotPositionKind.INTERNAL
                else LotPositionStatus.PENDING
            ),
            quantity=10.0,
            quantity_completed=0.0,
            creator_id=floor.graph.uid,
            lot_id=lot_id,
        )
    )
    await repo.save_step(
        make(
            LotStep,
            sequence=sequence,
            creator_id=floor.graph.uid,
            fabrication_method_id=method.id,
            lot_id=lot_id,
            position_id=position.id,
            source_process_id=None,
            estimated_setup_minutes=0,
        )
    )
    await floor.db.commit()
    return position


async def _queued(floor: Floor, position: LotPosition, quantity: float) -> ProductionOrder:
    machine = await floor.machine()
    saved = await SqlAlchemyProductionOrderRepository(floor.db).save(
        make(
            ProductionOrder,
            production_order_number=f"PO-B-{position.id}",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=position.id,
            quantity=quantity,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            creator_id=floor.graph.uid,
            machine_id=machine.id,
            lot_position_id=position.id,
        )
    )
    await floor.db.commit()
    return saved


async def test_an_order_queued_in_another_lot_waits_for_a_step_edit_of_the_project(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    project = await floor.graph.project()
    project.production_time_budget = 1000
    await SqlAlchemyProjectRepository(floor.db).save(project)
    await floor.db.commit()
    lot_a = await floor.lot()
    position_a = await _position(floor, lot_a.id, 1, LotPositionKind.INTERNAL)
    stored_a = await SqlAlchemyProductionLotRepository(floor.db).get_position_by_id(position_a.id)
    assert stored_a is not None
    position_a_step = stored_a.steps[0]
    await _queued(floor, position_a, 2.0)
    lot_b = await SqlAlchemyProductionLotRepository(floor.db).save(
        dataclasses.replace(lot_a, id=0, public_id=uuid4(), lot_number="L-B")
    )
    await floor.db.commit()
    queued_position = await _position(floor, lot_b.id, 1, LotPositionKind.INTERNAL)
    queued_b = await _queued(floor, queued_position, 2.0)
    open_position = await _position(floor, lot_b.id, 2, LotPositionKind.UNASSIGNED)
    machine = await floor.machine()

    gate = Gate("a")
    repository = SqlAlchemyProductionLotRepository
    monkeypatch.setattr(repository, "lock_time_budgets", gate.wrap(repository.lock_time_budgets))

    # The edit holds lot A and the project's queued orders, lot B's among
    # them, and stops before the time budget lock.
    edit = start(
        request(
            "a",
            engine_a,
            lot_deps.get_update_lot_step_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                position_a_step.id,
                UpdateLotStepCommand(
                    fabrication_method_id=position_a_step.fabrication_method_id,
                    note=None,
                    estimated_setup_minutes=0,
                    estimated_minutes_per_piece=4,
                ),
                lot_id=lot_a.id,
            ),
        )
    )
    await gate.wait_reached()
    assign = start(
        request(
            "b",
            engine_b,
            production_deps.get_assign_internal_position_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                lot_b.id,
                open_position.id,
                AssignInternalPositionCommand(
                    orders=[AssignInternalPositionOrderInput(machine_id=machine.id, quantity=3)]
                ),
            ),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    edited, assigned = await outcomes(edit, assign)

    assert not isinstance(edited, BaseException), edited
    assert not isinstance(assigned, BaseException), assigned
    async with sessions(engine_a)() as db:
        lots = SqlAlchemyProductionLotRepository(db)
        orders = SqlAlchemyProductionOrderRepository(db)
        live = [
            order
            for position_id in (queued_position.id, open_position.id)
            for order in await orders.get_by_lot_position_id(position_id)
        ]
        assert {o.lot_position_id for o in live} == {queued_position.id, open_position.id}
        for order in live:
            position = await lots.get_position_by_id(order.lot_position_id)
            assert position is not None
            assert all(s.time_budget_per_piece is not None for s in position.steps)
            assert order.estimated_duration_minutes == compute_estimated_duration_minutes(
                position.steps, order.quantity
            )
        stored_b = next(o for o in live if o.id == queued_b.id)
        assert stored_b.estimated_duration_minutes != 30
