"""
Races on the locks around the lifecycle rows, on a real Postgres: a line
added to an order while the order is being canceled, a demand and an order
line created for a project while the project is being deleted, a split and a reorder on one
queue, which both draw queue places and take the queue's lock before their
row locks, so they wait for each other instead of deadlocking, and two
deliveries whose line changed while they waited for its lock: one moved to
another order, which is refused, and one that gained a demand sorting
before the demand already held, which is locked late and fulfilled. A
deliver-all whose line moved while it waited skips that line as moved. A
project budget change and a lot quantity edit, which both recompute the
project's time budgets, wait for each other's rows instead of deadlocking.
"""

import asyncio
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.fulfillment.adapters.inbound.api.deps import allocations as allocation_deps
from src.modules.fulfillment.adapters.inbound.api.deps import demands as demand_deps
from src.modules.fulfillment.adapters.inbound.api.deps import lots as lot_deps
from src.modules.fulfillment.adapters.inbound.api.deps import orders as order_deps
from src.modules.fulfillment.adapters.inbound.api.deps import production as production_deps
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.bought_item_demand_dto import CreateDemandItemCommand
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.adapters.inbound.api.deps import products as project_deps
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.application.dto.project_dto import UpdateProjectCommand
from src.modules.workspace.domain.errors import ProjectDeleteBlockedError
from tests.integration.repository_reads._graph import TODAY
from tests.pg._floor import Floor
from tests.pg._race import Gate
from tests.pg._race import outcomes
from tests.pg._race import request
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_A
from tests.pg.conftest import RACE_B


async def test_an_order_cancel_refuses_a_line_added_after_it_read_the_lines(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, monkeypatch: Any
) -> None:
    line = await floor.bought_line(5.0)
    gate = Gate("a")
    repository = SqlAlchemyOrderItemRepository
    monkeypatch.setattr(
        repository, "get_by_order_id", gate.wrap(repository.get_by_order_id, after=True)
    )

    cancel = start(
        request(
            "a",
            engine_a,
            order_deps.get_cancel_order_use_case,
            lambda use_case: use_case.execute(floor.actor, line.order_id),
        )
    )
    await gate.wait_reached()
    added = await floor.bought_line(3.0)
    gate.release()
    [refused] = await outcomes(cancel)

    assert isinstance(refused, ConcurrentModificationError)
    async with sessions(engine_a)() as db:
        order = await SqlAlchemyOrderRepository(db).get_by_id(line.order_id)
        stored_line = await SqlAlchemyOrderItemRepository(db).get_by_id(added.id)
    assert order is not None and stored_line is not None
    assert order.canceled_at is None
    assert stored_line.canceled_at is None


async def test_a_project_delete_waits_for_a_demand_being_created_and_then_counts_it(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    project = await floor.graph.project()
    item = await floor.graph.bought_item()
    gate = Gate("a")
    repository = SqlAlchemyProjectRepository
    monkeypatch.setattr(
        repository, "lock_for_share", gate.wrap(repository.lock_for_share, after=True)
    )

    create = start(
        request(
            "a",
            engine_a,
            demand_deps.get_create_demand_item_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                CreateDemandItemCommand(
                    item_id=item.id, project_id=project.id, quantity=4.0, unit="pcs"
                ),
            ),
        )
    )
    await gate.wait_reached()
    delete = start(
        request(
            "b",
            engine_b,
            project_deps.get_delete_project_use_case,
            lambda use_case: use_case.execute(floor.actor, project.id),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    created, refused = await outcomes(create, delete)

    assert not isinstance(created, BaseException), created
    assert isinstance(refused, ProjectDeleteBlockedError)
    async with sessions(engine_a)() as db:
        assert await SqlAlchemyProjectRepository(db).get_by_id(project.id) is not None


async def test_a_project_delete_waits_for_an_order_line_being_created_and_then_counts_it(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    project = await floor.graph.project()
    item = await floor.graph.bought_item()
    order = await floor.graph.order()
    gate = Gate("a")
    repository = SqlAlchemyProjectRepository
    monkeypatch.setattr(
        repository, "lock_for_share", gate.wrap(repository.lock_for_share, after=True)
    )

    create = start(
        request(
            "a",
            engine_a,
            order_deps.get_create_order_item_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                CreateOrderItemCommand(
                    order_id=order.id,
                    supplier_id=order.supplier_id,
                    project_id=project.id,
                    bought_item_id=item.id,
                    quantity=4.0,
                    unit="pcs",
                ),
            ),
        )
    )
    await gate.wait_reached()
    delete = start(
        request(
            "b",
            engine_b,
            project_deps.get_delete_project_use_case,
            lambda use_case: use_case.execute(floor.actor, project.id),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    created, refused = await outcomes(create, delete)

    assert not isinstance(created, BaseException), created
    assert isinstance(refused, ProjectDeleteBlockedError), refused
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyProjectRepository(db).get_by_id(project.id)
    assert stored is not None
    assert not stored.deleted


async def test_a_split_and_a_reorder_of_one_queue_wait_for_each_other(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    machine = await floor.machine()
    first = await floor.queued_order(5.0, machine_id=machine.id, queue_sequence=1)
    second = await floor.queued_order(5.0, machine_id=machine.id, queue_sequence=2)
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(
        repository, "get_live_by_machine_ids", gate.wrap(repository.get_live_by_machine_ids)
    )

    reorder = start(
        request(
            "a",
            engine_a,
            production_deps.get_reorder_production_orders_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                machine.id,
                ReorderProductionOrdersCommand(ordered_production_order_ids=[second.id, first.id]),
            ),
        )
    )
    await gate.wait_reached()
    split = start(
        request(
            "b",
            engine_b,
            production_deps.get_split_production_order_use_case,
            lambda use_case: use_case.execute(
                floor.actor, first.id, SplitProductionOrderCommand(quantities=[3.0, 2.0])
            ),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    results = await outcomes(reorder, split)

    assert not any(isinstance(r, BaseException) for r in results), results
    async with sessions(engine_a)() as db:
        queue = await SqlAlchemyProductionOrderRepository(db).get_by_machine_id(machine.id)
    assert sorted(o.quantity for o in queue) == [2.0, 3.0, 5.0]


async def test_a_project_update_lets_a_row_that_references_the_project_be_inserted(
    floor: Floor, engine_b: AsyncEngine
) -> None:
    project = await floor.graph.project()
    await floor.graph.order()

    async with sessions(engine_b)() as updating:
        # The lock a project update or delete holds while it looks at the
        # project's work.
        await SqlAlchemyProjectRepository(updating).lock_for_update(project.id)
        # A line names the project; its foreign key check must not wait for
        # that lock, or an update that then locks lifecycle rows held by the
        # inserting transaction would deadlock with it.
        line = await asyncio.wait_for(floor.bought_line(2.0), 5.0)
        await updating.rollback()

    assert line.project_id == project.id


async def test_a_delivery_on_a_line_moved_while_it_waited_is_refused(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    line = await floor.bought_line(10.0)
    target = await floor.second_order()
    gate = Gate("b")
    repository = SqlAlchemyOrderItemRepository
    monkeypatch.setattr(repository, "next_position", gate.wrap(repository.next_position))

    move = start(
        request(
            "b",
            engine_b,
            order_deps.get_move_order_item_use_case,
            lambda use_case: use_case.execute(floor.actor, line.order_id, line.id, target.id),
        )
    )
    await gate.wait_reached()
    delivery = start(
        request(
            "a",
            engine_a,
            order_deps.get_process_order_item_delivery_use_case,
            lambda use_case: use_case.execute(floor.actor, line.id, quantity=4.0),
        )
    )
    await wait_for_lock(watcher, RACE_A)
    gate.release()
    moved, refused = await outcomes(move, delivery)

    assert not isinstance(moved, BaseException), moved
    assert isinstance(refused, ConcurrentModificationError), refused
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyOrderItemRepository(db).get_by_id(line.id)
    assert stored is not None
    assert stored.order_id == target.id
    assert stored.quantity_delivered == 0.0


async def test_deliver_all_skips_a_line_moved_while_it_waited(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    line = await floor.bought_line(10.0)
    kept = await floor.bought_line(5.0)
    target = await floor.second_order()
    gate = Gate("b")
    repository = SqlAlchemyOrderItemRepository
    monkeypatch.setattr(repository, "next_position", gate.wrap(repository.next_position))

    move = start(
        request(
            "b",
            engine_b,
            order_deps.get_move_order_item_use_case,
            lambda use_case: use_case.execute(floor.actor, line.order_id, line.id, target.id),
        )
    )
    await gate.wait_reached()
    deliver_all = start(
        request(
            "a",
            engine_a,
            order_deps.get_deliver_all_order_items_use_case,
            lambda use_case: use_case.execute(floor.actor, line.order_id),
        )
    )
    await wait_for_lock(watcher, RACE_A)
    gate.release()
    moved, delivered = await outcomes(move, deliver_all)

    assert not isinstance(moved, BaseException), moved
    assert not isinstance(delivered, BaseException), delivered
    assert [item.id for item in delivered.delivered] == [kept.id]
    assert [(s.order_item_id, s.reason) for s in delivered.skipped] == [(line.id, "moved")]
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyOrderItemRepository(db).get_by_id(line.id)
    assert stored is not None
    assert (stored.order_id, stored.quantity_delivered) == (target.id, 0.0)


async def test_a_delivery_locks_a_demand_allocated_to_its_line_while_it_waited(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    line = await floor.bought_line(10.0)
    # The demand allocated while the delivery waits sorts before the held one.
    early = await floor.bought_demand(5.0)
    held = await floor.bought_demand(5.0)
    create = allocation_deps.get_create_allocation_use_case

    def allocate(demand_id: int) -> Any:
        return lambda use_case: use_case.execute(
            floor.actor,
            CreateAllocationCommand(demand_item_id=demand_id, order_item_id=line.id, quantity=5.0),
        )

    await request("setup", engine_b, create, allocate(held.id))
    gate = Gate("b")
    repository = SqlAlchemyBoughtItemAllocationRepository
    monkeypatch.setattr(
        repository,
        "get_allocated_quantity_for_order_item",
        gate.wrap(repository.get_allocated_quantity_for_order_item),
    )

    allocation = start(request("b", engine_b, create, allocate(early.id)))
    await gate.wait_reached()
    delivery = start(
        request(
            "a",
            engine_a,
            order_deps.get_process_order_item_delivery_use_case,
            lambda use_case: use_case.execute(floor.actor, line.id, quantity=10.0),
        )
    )
    await wait_for_lock(watcher, RACE_A)
    gate.release()
    allocated, delivered = await outcomes(allocation, delivery)

    assert early.id < held.id
    assert not isinstance(allocated, BaseException), allocated
    assert not isinstance(delivered, BaseException), delivered
    async with sessions(engine_a)() as db:
        stored = [
            await SqlAlchemyBoughtItemDemandItemRepository(db).get_by_id(d.id)
            for d in (early, held)
        ]
    assert [d.status if d else None for d in stored] == ["fulfilled", "fulfilled"]


async def test_a_start_waits_for_auto_plan_on_its_queue_and_then_starts_the_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    machine = await floor.machine()
    order = await floor.queued_order(5.0, machine_id=machine.id, queue_sequence=1)
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    # Stopped in its write, holding the queue lock and the queued orders'
    # row locks, which the start has to wait for.
    monkeypatch.setattr(
        repository,
        "lock_for_update",
        gate.wrap(repository.lock_for_update, after=True),
    )

    plan = start(
        request(
            "a",
            engine_a,
            production_deps.get_auto_plan_use_case,
            lambda use_case: use_case.execute(
                floor.actor, AutoPlanCommand(machine_ids=[machine.id])
            ),
        )
    )
    await gate.wait_reached()
    started = start(
        request(
            "b",
            engine_b,
            production_deps.get_start_production_order_use_case,
            lambda use_case: use_case.execute(floor.actor, order.id, StartProductionOrderCommand()),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    planned, began = await outcomes(plan, started)

    assert not isinstance(planned, BaseException), planned
    assert not isinstance(began, BaseException), began
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyProductionOrderRepository(db).get_by_id(order.id)
    assert stored is not None and stored.status == "in_progress"


async def test_a_start_committed_while_auto_plan_reads_leaves_the_order_to_the_start(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    monkeypatch: Any,
) -> None:
    """Auto-Plan reads its queues without a lock, so a start commits during
    the read without waiting. The write reads the queue again under its
    locks, finds the order started, and leaves it alone."""
    machine = await floor.machine()
    order = await floor.queued_order(5.0, machine_id=machine.id, queue_sequence=1)
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(
        repository,
        "get_live_by_machine_ids",
        gate.wrap(repository.get_live_by_machine_ids, after=True),
    )

    plan = start(
        request(
            "a",
            engine_a,
            production_deps.get_auto_plan_use_case,
            lambda use_case: use_case.execute(
                floor.actor, AutoPlanCommand(machine_ids=[machine.id])
            ),
        )
    )
    await gate.wait_reached()
    began = await request(
        "b",
        engine_b,
        production_deps.get_start_production_order_use_case,
        lambda use_case: use_case.execute(floor.actor, order.id, StartProductionOrderCommand()),
    )
    gate.release()
    (planned,) = await outcomes(plan)

    assert not isinstance(planned, BaseException), planned
    assert began is not None
    assert [(s.order_id, s.reason) for s in planned.skipped] == [
        (order.id, "changed_while_planning")
    ]
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyProductionOrderRepository(db).get_by_id(order.id)
    assert stored is not None and stored.status == "in_progress"


async def test_a_project_budget_change_and_a_lot_quantity_edit_wait_instead_of_deadlocking(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    """Both recompute the project's time budgets. The budget lock comes
    after every row either locks, so the project update waits for the lot
    the edit holds instead of holding the budgets the edit waits for."""
    await floor.graph.made_allocation()
    lot = await floor.graph.lot()
    project = await floor.graph.project()
    gate = Gate("a")
    repository = SqlAlchemyProductionLotRepository
    monkeypatch.setattr(repository, "lock_time_budgets", gate.wrap(repository.lock_time_budgets))

    edit = start(
        request(
            "a",
            engine_a,
            lot_deps.get_update_lot_use_case,
            lambda use_case: use_case.execute(floor.actor, lot.id, UpdateLotCommand(quantity=8)),
        )
    )
    await gate.wait_reached()
    update = start(
        request(
            "b",
            engine_b,
            project_deps.get_update_project_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                project.id,
                UpdateProjectCommand(
                    project_number=project.project_number,
                    production_time_budget=(project.production_time_budget or 0) + 60,
                    required_delivery_date_made=TODAY + timedelta(days=30),
                    propagate_delivery_date_made=True,
                ),
            ),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    edited, updated = await outcomes(edit, update)

    assert not isinstance(edited, BaseException), edited
    assert not isinstance(updated, BaseException), updated


async def _pending_line(floor: Floor, order_id: int) -> OrderItem:
    """A pending bought line on the order, as a buyer adds one."""
    template = await floor.bought_line(1.0)
    async with sessions(floor.db.bind)() as db:  # type: ignore[arg-type]
        line = await SqlAlchemyOrderItemRepository(db).get_by_id(template.id)
        assert line is not None
        line.status = OrderItemStatus.PENDING
        line.ordered_date = None
        line.order_id = order_id
        saved = await SqlAlchemyOrderItemRepository(db).save(line)
        await db.commit()
    return saved


async def test_an_order_submit_refuses_a_line_added_after_it_read_the_lines(
    floor: Floor, engine_a: AsyncEngine, monkeypatch: Any
) -> None:
    draft = await floor.second_order()
    async with sessions(engine_a)() as db:
        order = await SqlAlchemyOrderRepository(db).get_by_id(draft.id)
        assert order is not None
        order.status = OrderStatus.DRAFT
        order.ordered_date = None
        await SqlAlchemyOrderRepository(db).save(order)
        await db.commit()
    await _pending_line(floor, draft.id)
    gate = Gate("a")
    repository = SqlAlchemyOrderItemRepository
    monkeypatch.setattr(
        repository, "get_by_order_id", gate.wrap(repository.get_by_order_id, after=True)
    )

    submit = start(
        request(
            "a",
            engine_a,
            order_deps.get_submit_order_use_case,
            lambda use_case: use_case.execute(floor.actor, draft.id),
        )
    )
    await gate.wait_reached()
    await _pending_line(floor, draft.id)
    gate.release()
    [refused] = await outcomes(submit)

    assert isinstance(refused, ConcurrentModificationError), refused
