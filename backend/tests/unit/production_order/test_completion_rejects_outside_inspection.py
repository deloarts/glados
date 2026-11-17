"""
Only an inspection completion may reject pieces, because only its
disposition accounts for them. An ordinary completion that rejects pieces,
or names rework or scrap, is refused with
ProductionOrderCompletionSplitInvalidError (422) before anything is
written. No database, no HTTP.
"""

from datetime import date

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import ProductionOrderCompletionSplitInvalidError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderFileRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import production_order_reconciler


@pytest.mark.parametrize(
    "split",
    [
        {"quantity_accepted": 4.0, "quantity_rejected": 1.0},
        {"quantity_accepted": 0.0, "quantity_rejected": 5.0, "quantity_scrap": 5.0},
        {"quantity_scrap": 1.0},
        {"quantity_rework": 1.0},
    ],
    ids=["rejects", "rejects-with-scrap", "scrap", "rework"],
)
async def test_an_ordinary_completion_cannot_reject_pieces(split: dict[str, float]) -> None:
    position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
    lot = make_lot(positions=[position])
    lot.source_made_item_id = 99
    lot_repo = FakeProductionLotRepository([lot])
    order = make_order(
        id=1, lot_position_id=1, quantity=10.0, status=ProductionOrderStatus.IN_PROGRESS
    )
    order_repo = FakeProductionOrderRepository([order])
    bus = FakeEventBus()
    uow = FakeUnitOfWork()
    use_case = RecordProductionOrderCompletion(
        order_repo,
        lot_repo,
        FakeProductionOrderFileRepository(),
        event_bus=bus,
        uow=uow,
        reconciler=production_order_reconciler(order_repo, lot_repo, bus),
        made_item_demand_repo=FakeMadeItemDemandRepository(),
        made_item_allocation_repo=FakeMadeItemAllocationRepository(),
        create_lot=NoLotCreation(),
        **completion_collaborators(order_repo),
    )

    with pytest.raises(ProductionOrderCompletionSplitInvalidError, match="inspection"):
        await use_case.execute(
            make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS]),
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=5.0, completion_date=date(2026, 1, 2), **split
            ),
        )

    assert await order_repo.get_completions(1) == []
    assert order.quantity_completed == 0.0
    assert order.status == ProductionOrderStatus.IN_PROGRESS.value
    assert position.quantity_completed == 0.0
    assert lot_repo.lock_calls == []
    assert bus.published == []
    assert uow.commits == 0
