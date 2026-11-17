"""
PrintLotScrapTag: the lot-scoped manual scrap tag print action. Its own
job is entirely the "which record carries this lot's latest scrap
disposition" scan across every position (completions for internal/mixed
positions, lost deliveries for external/mixed ones); the actual print
pipeline is a plain PrintDocument.execute() call, faked out here.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.facade.lot_scrap_records import LotScrapRecords
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.quality.application.use_cases.print_document.print_lot_scrap_tag import (
    PrintLotScrapTag,
)
from src.modules.quality.domain.errors import ScrapTagRecordNotFoundError
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository


class FakeProductionOrderRepositoryWithCompletions:
    def __init__(self, orders=None, completions_by_order=None) -> None:
        self._orders_by_position: dict[int, list] = {}
        for order in orders or []:
            self._orders_by_position.setdefault(order.lot_position_id, []).append(order)
        self._completions = completions_by_order or {}

    async def get_by_lot_position_id(self, lot_position_id: int):
        return self._orders_by_position.get(lot_position_id, [])

    async def get_completions(self, production_order_id: int):
        return self._completions.get(production_order_id, [])


class FakeOrderItemDeliveryRepository:
    def __init__(self, deliveries_by_item=None) -> None:
        self._deliveries = deliveries_by_item or {}

    async def get_by_order_item_id(self, order_item_id: int):
        return self._deliveries.get(order_item_id, [])


class FakePrintDocument:
    def __init__(self):
        self.calls: list[dict] = []

    async def execute(self, actor, classifier, root_type, root_id, **kwargs):
        self.calls.append(
            {
                "actor": actor,
                "classifier": classifier,
                "root_type": root_type,
                "root_id": root_id,
                **kwargs,
            }
        )
        return "print-job-result"


def make_position(
    id: int, lot_id: int, sequence: int = 1, kind: LotPositionKind = LotPositionKind.INTERNAL
) -> LotPosition:
    return LotPosition(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=LotPositionStatus.IN_PROGRESS,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=lot_id,
    )


def make_lot(id: int = 1) -> ProductionLot:
    return ProductionLot(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number=f"LOT-26-{id:05d}",
        quantity=8.0,
        status=LotStatus.IN_PROGRESS,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=42,
        project_id=1,
        input_demand_id=None,
    )


class _StubCompletion:
    def __init__(self, id: int, quantity_scrap: float, created: datetime) -> None:
        self.id = id
        self.quantity_scrap = quantity_scrap
        self.created = created


class _StubDelivery:
    def __init__(
        self, id: int, quantity_rejected: float, rejection_outcome: str | None, created: datetime
    ) -> None:
        self.id = id
        self.quantity_rejected = quantity_rejected
        self.rejection_outcome = rejection_outcome
        self.created = created


def build_use_case(
    *,
    lots: FakeProductionLotRepository,
    orders=None,
    completions_by_order=None,
    order_items=None,
    deliveries_by_item=None,
) -> tuple[PrintLotScrapTag, FakePrintDocument]:
    printer = FakePrintDocument()
    use_case = PrintLotScrapTag(
        scrap_records=LotScrapRecords(
            lot_repo=lots,
            production_order_repo=FakeProductionOrderRepositoryWithCompletions(
                orders, completions_by_order
            ),
            order_item_repo=FakeOrderItemRepository(order_items or []),
            order_item_delivery_repo=FakeOrderItemDeliveryRepository(deliveries_by_item),
        ),
        print_document=printer,
    )
    return use_case, printer


class TestPrintLotScrapTag:
    async def test_raises_when_the_lot_does_not_exist(self):
        use_case, _ = build_use_case(lots=FakeProductionLotRepository())
        with pytest.raises(LotNotFoundError):
            await use_case.execute(make_user(), 999)

    async def test_raises_when_the_lot_has_no_scrap_record(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        await lots.save_position(make_position(0, lot.id))
        use_case, _ = build_use_case(lots=lots)

        with pytest.raises(ScrapTagRecordNotFoundError):
            await use_case.execute(make_user(), lot.id)

    async def test_prints_from_the_lots_one_scrap_completion(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id))
        order = make_production_order(1, lot_position_id=position.id)
        completion = _StubCompletion(5, 2.0, datetime(2026, 9, 20, 10, 0, tzinfo=UTC))

        use_case, printer = build_use_case(
            lots=lots, orders=[order], completions_by_order={order.id: [completion]}
        )
        actor = make_user()
        result = await use_case.execute(actor, lot.id, printer_id=3, copies=2)

        assert result == "print-job-result"
        assert len(printer.calls) == 1
        call = printer.calls[0]
        assert call["classifier"] == "scrap_tag"
        assert call["root_type"] == "production_order_completion"
        assert call["root_id"] == 5
        assert call["printer_id"] == 3
        assert call["copies"] == 2
        assert call["trigger"] == "manual"

    async def test_prints_from_the_lots_one_lost_delivery(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id, kind=LotPositionKind.EXTERNAL))
        item = make_order_item(id=7, lot_position_id=position.id)
        delivery = _StubDelivery(9, 1.0, "lost", datetime(2026, 9, 21, 9, 0, tzinfo=UTC))

        use_case, printer = build_use_case(
            lots=lots, order_items=[item], deliveries_by_item={item.id: [delivery]}
        )
        await use_case.execute(make_user(), lot.id)

        call = printer.calls[0]
        assert call["root_type"] == "order_item_delivery"
        assert call["root_id"] == 9

    async def test_a_redeliver_outcome_delivery_is_not_a_scrap_record(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id, kind=LotPositionKind.EXTERNAL))
        item = make_order_item(id=7, lot_position_id=position.id)
        delivery = _StubDelivery(9, 1.0, "redeliver", datetime(2026, 9, 21, 9, 0, tzinfo=UTC))

        use_case, _ = build_use_case(
            lots=lots, order_items=[item], deliveries_by_item={item.id: [delivery]}
        )
        with pytest.raises(ScrapTagRecordNotFoundError):
            await use_case.execute(make_user(), lot.id)

    async def test_the_most_recent_scrap_record_across_positions_wins(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        internal = await lots.save_position(make_position(0, lot.id, sequence=1))
        external = await lots.save_position(
            make_position(0, lot.id, sequence=2, kind=LotPositionKind.EXTERNAL)
        )
        order = make_production_order(1, lot_position_id=internal.id)
        item = make_order_item(id=7, lot_position_id=external.id)

        earlier_completion = _StubCompletion(5, 1.0, datetime(2026, 9, 20, 8, 0, tzinfo=UTC))
        later_delivery = _StubDelivery(9, 1.0, "lost", datetime(2026, 9, 21, 9, 0, tzinfo=UTC))

        use_case, printer = build_use_case(
            lots=lots,
            orders=[order],
            completions_by_order={order.id: [earlier_completion]},
            order_items=[item],
            deliveries_by_item={item.id: [later_delivery]},
        )
        await use_case.execute(make_user(), lot.id)

        call = printer.calls[0]
        assert call["root_type"] == "order_item_delivery"
        assert call["root_id"] == 9
