"""
Two requests that write the same lifecycle rows at the same time, on a real
Postgres. In each test the first request stops inside the use case after
it took its locks, the second one is shown to wait for one of them, and
then both run to their end; the committed state is asserted afterwards.
The lock order lot, production order, order, order item, demand makes the
second request read what the first committed, so the invariant the first
one checked still holds for the second, and the version column refuses a
write from a copy older than the row.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm.exc import StaleDataError

from src.modules.fulfillment.adapters.inbound.api.deps import allocations as allocation_deps
from src.modules.fulfillment.adapters.inbound.api.deps import lots as lot_deps
from src.modules.fulfillment.adapters.inbound.api.deps import orders as order_deps
from src.modules.fulfillment.adapters.inbound.api.deps import production as production_deps
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
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
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.platform.adapters.inbound.api.exception_handlers import stale_data_error_handler
from src.modules.platform.domain.exceptions import DomainError
from tests.integration._tenant_day import tenant_today
from tests.pg._floor import Floor
from tests.pg._race import Gate
from tests.pg._race import outcomes
from tests.pg._race import request
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_A
from tests.pg.conftest import RACE_B

_COMPLETE = production_deps.get_record_production_order_completion_use_case


def _complete(actor: Any, order_id: int, quantity: float) -> Any:
    # The tenant's day, which the use case reads the order's start in, not
    # the UTC day: the two differ for an hour or two after local midnight.
    return lambda use_case: use_case.execute(
        actor,
        order_id,
        RecordProductionOrderCompletionCommand(quantity=quantity, completion_date=tenant_today()),
    )


async def _production_order(engine: AsyncEngine, order_id: int) -> Any:
    async with sessions(engine)() as db:
        return await SqlAlchemyProductionOrderRepository(db).get_by_id(order_id)


async def _lot(engine: AsyncEngine, lot_id: int) -> Any:
    async with sessions(engine)() as db:
        return await SqlAlchemyProductionLotRepository(db).get_by_id(lot_id)


async def test_two_completions_cannot_exceed_the_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    order = await floor.running_order()
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(repository, "get_completions", gate.wrap(repository.get_completions))

    first = start(request("a", engine_a, _COMPLETE, _complete(floor.actor, order.id, 6.0)))
    await gate.wait_reached()
    second = start(request("b", engine_b, _COMPLETE, _complete(floor.actor, order.id, 6.0)))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    done, refused = await outcomes(first, second)

    assert not isinstance(done, BaseException)
    assert isinstance(refused, DomainError)
    stored = await _production_order(engine_a, order.id)
    assert (stored.status, stored.quantity_completed) == ("in_progress", 6.0)


async def test_the_last_deliveries_of_two_sibling_lines_deliver_the_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    first_line = await floor.bought_line(5.0)
    second_line = await floor.bought_line(5.0)
    gate = Gate("a")
    repository = SqlAlchemyOrderItemRepository
    monkeypatch.setattr(repository, "save", gate.wrap(repository.save))
    deliver = order_deps.get_process_order_item_delivery_use_case

    def delivery(line_id: int) -> Any:
        return lambda use_case: use_case.execute(floor.actor, line_id, quantity=5.0)

    first = start(request("a", engine_a, deliver, delivery(first_line.id)))
    await gate.wait_reached()
    second = start(request("b", engine_b, deliver, delivery(second_line.id)))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    results = await outcomes(first, second)

    assert not any(isinstance(r, BaseException) for r in results), results
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyOrderRepository(db).get_by_id(first_line.order_id)
    assert stored is not None
    assert stored.status == "delivered"


async def test_two_receipts_of_one_line_cannot_book_more_than_it_awaits(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    """Two receivers book the same line at once: the second waits for the
    first one's lock and then sees what it delivered, so it cannot take the
    line beyond what it awaits."""
    line = await floor.bought_line(5.0)
    gate = Gate("a")
    repository = SqlAlchemyOrderItemRepository
    monkeypatch.setattr(repository, "save", gate.wrap(repository.save))
    deliver = order_deps.get_process_order_item_delivery_use_case

    def delivery(use_case: Any) -> Any:
        return use_case.execute(floor.actor, line.id, quantity=3.0)

    first = start(request("a", engine_a, deliver, delivery))
    await gate.wait_reached()
    second = start(request("b", engine_b, deliver, delivery))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    done, refused = await outcomes(first, second)

    assert not isinstance(done, BaseException), done
    assert isinstance(refused, DomainError), refused
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyOrderItemRepository(db).get_by_id(line.id)
    assert stored is not None
    assert (stored.quantity_delivered, stored.status) == (3.0, "partially_delivered")


async def test_a_hold_racing_the_final_completion_leaves_the_lot_completed(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    order = await floor.running_order()
    await request("a", engine_a, _COMPLETE, _complete(floor.actor, order.id, 4.0))
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(repository, "get_completions", gate.wrap(repository.get_completions))

    lot_id = (await floor.lot()).id

    def hold(use_case: Any) -> Any:
        return use_case.execute(floor.actor, lot_id, HoldLotCommand(reason="Coolant leak"))

    first = start(request("a", engine_a, _COMPLETE, _complete(floor.actor, order.id, 6.0)))
    await gate.wait_reached()
    second = start(request("b", engine_b, lot_deps.get_hold_lot_use_case, hold))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    done, refused = await outcomes(first, second)

    assert not isinstance(done, BaseException)
    assert isinstance(refused, DomainError)
    assert (await _lot(engine_a, lot_id)).status == "completed"
    assert (await _production_order(engine_a, order.id)).status == "completed"


async def test_a_resume_racing_a_cancel_never_revives_the_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    order = await floor.running_order()
    await request(
        "a",
        engine_a,
        production_deps.get_pause_production_order_use_case,
        lambda use_case: use_case.execute(floor.actor, order.id, PauseProductionOrderCommand()),
    )
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(repository, "save", gate.wrap(repository.save))

    first = start(
        request(
            "a",
            engine_a,
            production_deps.get_cancel_production_order_use_case,
            lambda use_case: use_case.execute(
                floor.actor, order.id, CancelProductionOrderCommand(reason="Customer withdrew")
            ),
        )
    )
    await gate.wait_reached()
    second = start(
        request(
            "b",
            engine_b,
            production_deps.get_start_production_order_use_case,
            lambda use_case: use_case.execute(floor.actor, order.id, StartProductionOrderCommand()),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    done, refused = await outcomes(first, second)

    assert not isinstance(done, BaseException)
    assert isinstance(refused, DomainError)
    assert (await _production_order(engine_a, order.id)).status == "canceled"


async def test_two_allocations_cannot_overfill_one_line(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    line = await floor.bought_line(10.0)
    demands = [await floor.bought_demand(10.0), await floor.bought_demand(10.0)]
    gate = Gate("a")
    repository = SqlAlchemyBoughtItemAllocationRepository
    monkeypatch.setattr(
        repository,
        "get_allocated_quantity_for_order_item",
        gate.wrap(repository.get_allocated_quantity_for_order_item),
    )
    create = allocation_deps.get_create_allocation_use_case

    def allocate(demand_id: int) -> Any:
        return lambda use_case: use_case.execute(
            floor.actor,
            CreateAllocationCommand(demand_item_id=demand_id, order_item_id=line.id, quantity=6.0),
        )

    first = start(request("a", engine_a, create, allocate(demands[0].id)))
    await gate.wait_reached()
    second = start(request("b", engine_b, create, allocate(demands[1].id)))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    done, refused = await outcomes(first, second)

    assert not isinstance(done, BaseException)
    assert isinstance(refused, DomainError)
    async with sessions(engine_a)() as db:
        allocated = await SqlAlchemyBoughtItemAllocationRepository(
            db
        ).get_allocated_quantity_for_order_item(line.id)
    assert allocated == 6.0


async def test_a_schedule_recompute_keeps_a_machine_reassigned_during_its_walk(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, monkeypatch: Any
) -> None:
    first_machine = await floor.machine()
    second_machine = await floor.second_machine()
    order = await floor.queued_order(10.0, machine_id=first_machine.id, queue_sequence=1)
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(
        repository,
        "get_all_non_terminal",
        gate.wrap(repository.get_all_non_terminal, after=True),
    )

    walk = start(
        request(
            "a",
            engine_a,
            production_deps.get_recompute_machine_schedule_use_case,
            lambda use_case: use_case.execute_all(),
        )
    )
    await gate.wait_reached()
    await request(
        "b",
        engine_b,
        production_deps.get_reassign_production_order_machine_use_case,
        lambda use_case: use_case.execute(
            floor.actor,
            order.id,
            ReassignProductionOrderMachineCommand(machine_id=second_machine.id),
        ),
    )
    gate.release()
    [walked] = await outcomes(walk)

    assert not isinstance(walked, BaseException), walked
    assert (await _production_order(engine_a, order.id)).machine_id == second_machine.id


async def test_a_completion_and_a_scrap_on_one_lot_both_finish_in_lock_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    order = await floor.running_order()
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(repository, "get_completions", gate.wrap(repository.get_completions))

    first = start(request("a", engine_a, _COMPLETE, _complete(floor.actor, order.id, 3.0)))
    await gate.wait_reached()
    second = start(
        request(
            "b",
            engine_b,
            production_deps.get_scrap_production_pieces_use_case,
            lambda use_case: use_case.execute(
                floor.actor,
                ScrapProductionPiecesCommand(
                    production_order_id=order.id,
                    quantity=2.0,
                    reason=ScrapReason.MATERIAL_DEFECT,
                    create_replacement=False,
                ),
            ),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    results = await outcomes(first, second)

    assert not any(isinstance(r, BaseException) for r in results), results
    stored = await _production_order(engine_a, order.id)
    assert stored.quantity_completed == 3.0


async def test_a_write_from_a_copy_older_than_the_row_is_refused_with_409(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine
) -> None:
    order_id = (await floor.graph.order()).id

    async with sessions(engine_a)() as mine, sessions(engine_b)() as theirs:
        their_order = await SqlAlchemyOrderRepository(theirs).get_by_id(order_id)
        assert their_order is not None
        their_order.note = "theirs"
        await SqlAlchemyOrderRepository(theirs).save(their_order)

        async def write_mine() -> None:
            my_order = await SqlAlchemyOrderRepository(mine).get_by_id(order_id)
            assert my_order is not None
            my_order.note = "mine"
            await SqlAlchemyOrderRepository(mine).save(my_order)

        writing = start(write_mine())
        await wait_for_lock(watcher, RACE_A)
        await theirs.commit()
        [refused] = await outcomes(writing)
        await mine.rollback()

    assert isinstance(refused, StaleDataError)
    response = await stale_data_error_handler(None, refused)  # type: ignore[arg-type]
    assert response.status_code == 409
    async with sessions(engine_a)() as db:
        stored = await SqlAlchemyOrderRepository(db).get_by_id(order_id)
    assert stored is not None
    assert stored.note == "theirs"


async def test_a_reversal_waits_for_a_completion_on_the_same_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    # The reversal reads the position's completed count under the lot lock,
    # so it sees the completion that committed while it waited.
    order = await floor.running_order()
    await request("setup", engine_a, _COMPLETE, _complete(floor.actor, order.id, 4.0))
    [first] = (await _production_order(engine_a, order.id)).completions
    gate = Gate("a")
    repository = SqlAlchemyProductionOrderRepository
    monkeypatch.setattr(repository, "get_completions", gate.wrap(repository.get_completions))

    completing = start(request("a", engine_a, _COMPLETE, _complete(floor.actor, order.id, 3.0)))
    await gate.wait_reached()
    reversing = start(
        request(
            "b",
            engine_b,
            production_deps.get_reverse_production_order_completion_use_case,
            lambda use_case: use_case.execute(floor.actor, order.id, first.id, "Miscounted"),
        )
    )
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    completed, reversed_ = await outcomes(completing, reversing)

    assert not isinstance(completed, BaseException), completed
    assert not isinstance(reversed_, BaseException), reversed_
    stored = await _production_order(engine_a, order.id)
    assert (stored.quantity_completed, stored.pieces_processed) == (3.0, 3.0)
