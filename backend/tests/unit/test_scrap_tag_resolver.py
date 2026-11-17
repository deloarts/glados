"""
PrintRootResolver's two scrap_tag root types: PRODUCTION_ORDER_COMPLETION
(internal scrap during production) and ORDER_ITEM_DELIVERY (lost at goods
receipt). Both funnel into the same ScrapTagResult shape so the seeded
scrap_tag ZPL template's field_map works regardless of which record a
given occurrence was recorded on.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.dto.production_lot_dto import ScrapTagResult
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.production_lot import FollowUpLotSummary
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.quality.application.services.print_classifiers import triggers_for
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.read.application.services.print_root_resolver import PrintRootResolver
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeBoughtItemRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeSourceItemRepository


class FakeProductionOrderRepositoryWithCompletions:
    """Minimal, local (not fakes.py's shared FakeProductionOrderRepository,
    which has no get_by_id/get_completion_by_id) production order fake for
    scrap_tag resolution: get_by_id for the completion's own order, and a
    completions store keyed by id."""

    def __init__(self, orders=None, completions=None) -> None:
        self._orders = {o.id: o for o in (orders or [])}
        self._completions = {c.id: c for c in (completions or [])}

    async def get_by_id(self, id: int):
        return self._orders.get(id)

    async def get_completion_by_id(self, completion_id: int):
        return self._completions.get(completion_id)


class FakeOrderItemDeliveryRepositoryById:
    def __init__(self, deliveries=None) -> None:
        self._deliveries = {d.id: d for d in (deliveries or [])}

    async def get_by_id(self, id: int):
        return self._deliveries.get(id)


def make_position(
    id: int, lot_id: int, kind: LotPositionKind = LotPositionKind.INTERNAL
) -> LotPosition:
    return LotPosition(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=1,
        kind=kind,
        status=LotPositionStatus.IN_PROGRESS,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=lot_id,
    )


def make_lot(
    id: int = 1,
    *,
    follow_up_lots: list[FollowUpLotSummary] | None = None,
) -> ProductionLot:
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
        made_item_part_number="PN-42",
        made_item_article_name="Bracket",
        made_item_revision="A",
        follow_up_lots=follow_up_lots or [],
    )


def make_completion(
    id: int = 1,
    *,
    production_order_id: int = 1,
    quantity_scrap: float = 2.0,
    scrap_reason: ScrapReason | None = ScrapReason.TOOL_BREAKAGE,
    created: datetime | None = None,
    operator=None,
) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=id,
        production_order_id=production_order_id,
        quantity=quantity_scrap,
        quantity_accepted=0.0,
        quantity_rejected=quantity_scrap,
        quantity_scrap=quantity_scrap,
        scrap_reason=scrap_reason,
        completion_date=date(2026, 9, 20),
        note=None,
        operator_id=5,
        recorded_by_id=1,
        created=created or datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
        operator=operator,
    )


def make_delivery(
    id: int = 1,
    *,
    order_item_id: int = 1,
    quantity_rejected: float = 1.0,
    rejection_reason: str | None = "supplier_damage",
    rejection_outcome: RejectionOutcome | None = RejectionOutcome.LOST,
    created: datetime | None = None,
    receiver=None,
) -> OrderItemDelivery:
    return OrderItemDelivery(
        id=id,
        order_item_id=order_item_id,
        quantity=1.0,
        delivery_date=datetime(2026, 9, 21, tzinfo=UTC),
        storage_place=None,
        receiver_id=7,
        created=created or datetime(2026, 9, 21, 9, 0, tzinfo=UTC),
        quantity_rejected=quantity_rejected,
        rejection_reason=rejection_reason,
        rejection_outcome=rejection_outcome,
        receiver=receiver,
    )


def build_resolver(
    *,
    orders=None,
    completions=None,
    deliveries=None,
    lots: FakeProductionLotRepository | None = None,
    order_items=None,
) -> PrintRootResolver:
    return PrintRootResolver(
        order_repo=FakeOrderRepository([]),
        order_item_repo=FakeOrderItemRepository(order_items or []),
        production_order_repo=FakeProductionOrderRepositoryWithCompletions(orders, completions),
        production_lot_repo=lots or FakeProductionLotRepository(),
        made_item_repo=FakeMadeItemRepository([]),
        bought_item_repo=FakeBoughtItemRepository([]),
        source_item_repo=FakeSourceItemRepository([]),
        order_item_delivery_repo=FakeOrderItemDeliveryRepositoryById(deliveries),
    )


class TestScrapTagClassifierWiring:
    def test_scrap_tag_offers_only_pieces_scrapped_as_a_trigger(self):
        assert triggers_for(PrintClassifier.SCRAP_TAG) == [PrintTrigger.PIECES_SCRAPPED]


class TestScrapTagFromCompletion:
    async def test_resolves_the_full_scrap_tag_shape(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id))
        order = make_production_order(1, lot_position_id=position.id)
        operator = make_user(id=5)
        completion = make_completion(1, production_order_id=1, operator=operator)

        resolver = build_resolver(orders=[order], completions=[completion], lots=lots)
        root = await resolver.resolve(PrintRootType.PRODUCTION_ORDER_COMPLETION.value, 1)

        assert isinstance(root, ScrapTagResult)
        assert root.id == 1
        assert root.lot_id == lot.id
        assert root.lot_number == lot.lot_number
        assert root.made_item_label == "PN-42 rev A - Bracket"
        assert root.quantity == 2.0
        assert root.reason == "tool_breakage"
        assert root.reason_label == "Tool breakage"
        assert root.scrap_date == date(2026, 9, 20)
        assert root.operator_full_name == operator.full_name
        assert root.replacement_lot_id is None
        assert root.replacement_lot_number == ""

    async def test_none_when_the_completion_carries_no_scrap(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id))
        order = make_production_order(1, lot_position_id=position.id)
        completion = make_completion(1, production_order_id=1, quantity_scrap=0.0)

        resolver = build_resolver(orders=[order], completions=[completion], lots=lots)
        assert await resolver.resolve(PrintRootType.PRODUCTION_ORDER_COMPLETION.value, 1) is None

    async def test_none_for_an_unknown_completion_id(self):
        resolver = build_resolver()
        assert await resolver.resolve(PrintRootType.PRODUCTION_ORDER_COMPLETION.value, 999) is None

    async def test_picks_the_earliest_replacement_lot_created_at_or_after_this_occurrence(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id))
        order = make_production_order(1, lot_position_id=position.id)
        completion = make_completion(
            1, production_order_id=1, created=datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
        )

        # An earlier replacement lot (from a prior, unrelated scrap event on
        # this same origin) must be ignored; only the one created at/after
        # this completion's own timestamp counts.
        earlier_replacement = make_lot(id=2)
        earlier_replacement.created = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
        await lots.save(earlier_replacement)

        this_replacement = make_lot(id=3)
        this_replacement.created = datetime(2026, 9, 20, 10, 5, tzinfo=UTC)
        await lots.save(this_replacement)

        lot.follow_up_lots = [
            FollowUpLotSummary(
                id=2,
                lot_number=earlier_replacement.lot_number,
                disposition=LotOriginDisposition.REPLACEMENT,
                quantity=1,
            ),
            FollowUpLotSummary(
                id=3,
                lot_number=this_replacement.lot_number,
                disposition=LotOriginDisposition.REPLACEMENT,
                quantity=2,
            ),
        ]

        resolver = build_resolver(orders=[order], completions=[completion], lots=lots)
        root = await resolver.resolve(PrintRootType.PRODUCTION_ORDER_COMPLETION.value, 1)

        assert root is not None
        assert root.replacement_lot_id == 3
        assert root.replacement_lot_number == this_replacement.lot_number


class TestScrapTagFromDelivery:
    async def test_resolves_the_full_scrap_tag_shape(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id, kind=LotPositionKind.EXTERNAL))
        item = make_order_item(id=1, lot_position_id=position.id)
        receiver = make_user(id=7)
        delivery = make_delivery(1, order_item_id=1, receiver=receiver)

        resolver = build_resolver(deliveries=[delivery], lots=lots, order_items=[item])
        root = await resolver.resolve(PrintRootType.ORDER_ITEM_DELIVERY.value, 1)

        assert isinstance(root, ScrapTagResult)
        assert root.id == 1
        assert root.lot_id == lot.id
        assert root.quantity == 1.0
        assert root.reason == "supplier_damage"
        assert root.reason_label == "Supplier damage"
        assert root.scrap_date == date(2026, 9, 21)
        assert root.operator_full_name == receiver.full_name

    async def test_none_for_a_redeliver_outcome(self):
        lots = FakeProductionLotRepository()
        lot = await lots.save(make_lot(id=0))
        position = await lots.save_position(make_position(0, lot.id, kind=LotPositionKind.EXTERNAL))
        item = make_order_item(id=1, lot_position_id=position.id)
        delivery = make_delivery(1, order_item_id=1, rejection_outcome=RejectionOutcome.REDELIVER)

        resolver = build_resolver(deliveries=[delivery], lots=lots, order_items=[item])
        assert await resolver.resolve(PrintRootType.ORDER_ITEM_DELIVERY.value, 1) is None

    async def test_none_when_the_delivery_repo_is_not_wired(self):
        resolver = PrintRootResolver(
            order_repo=FakeOrderRepository([]),
            order_item_repo=FakeOrderItemRepository([]),
            production_order_repo=FakeProductionOrderRepositoryWithCompletions(),
            production_lot_repo=FakeProductionLotRepository(),
            made_item_repo=FakeMadeItemRepository([]),
            bought_item_repo=FakeBoughtItemRepository([]),
            source_item_repo=FakeSourceItemRepository([]),
        )
        assert await resolver.resolve(PrintRootType.ORDER_ITEM_DELIVERY.value, 1) is None
