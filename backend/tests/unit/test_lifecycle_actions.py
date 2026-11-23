"""
The `actions` a result carries are the ones the aggregate's intent table
allows the reading user now (application/services/lifecycle_actions.py),
with the context the service reads for it: the order of a line, the lot of
a MADE line or of a position, and whether a demand holds allocations.
"""

from typing import Any

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import LotResponse
from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryStepResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.mappers.bought_item_demand_mapper import (
    BoughtItemDemandItemMapper,
)
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LotContext
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit.lifecycle.test_intents import _user
from tests.unit.test_lifecycle_intent_mapping import make
from tests.unit.test_lifecycle_intent_mapping import respond

READER = _user(2, Permission.WRITE_ORDERS, Permission.WRITE_LOTS)
MANAGER = _user(9, Permission.MANAGE_ORDERS, Permission.MANAGE_LOTS)


class _ByIds:
    """A repository fake that answers get_by_ids and counts the calls."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = {row.id: row for row in rows}
        self.calls: list[list[int]] = []

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Any]:
        self.calls.append(list(ids))
        return [self._rows[i] for i in ids if i in self._rows]


class _Allocations:
    def __init__(self, demand_ids: list[int]) -> None:
        self._demand_ids = demand_ids

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        return [
            make(
                BoughtItemDemandAllocation,
                demand_item_id=i,
                source=AllocationSource.ORDER,
                quantity=1.0,
            )
            for i in demand_item_ids
            if i in self._demand_ids
        ]


def _order(order_id: int, status: OrderStatus) -> Order:
    return make(Order, id=order_id, status=status)


def _order_result(order_id: int, status: OrderStatus, *items: OrderItem) -> OrderResult:
    return OrderMapper.to_result(_order(order_id, status), items=list(items))


def _line(item_id: int, status: OrderItemStatus, **values: Any) -> OrderItem:
    values.setdefault("line_type", OrderLineType.BOUGHT)
    values.setdefault("order_id", 1)
    values.setdefault("quantity", 10.0)
    values.setdefault("quantity_delivered", 0.0)
    values.setdefault("quantity_rejected", 0.0)
    values.setdefault("quantity_rejected_lost", 0.0)
    return make(OrderItem, id=item_id, status=status, **values)


def _lot(lot_id: int, status: LotStatus, **values: Any) -> ProductionLot:
    values.setdefault("quantity", 5.0)
    values.setdefault("priority", UrgencyClass.NORMAL)
    return make(ProductionLot, id=lot_id, status=status, **values)


# ── Orders and their lines ──────────────────────────────────────────────


async def test_an_order_offers_what_its_table_allows_and_cancel_past_requested_needs_manage():
    draft = _order_result(1, OrderStatus.DRAFT)
    ordered = _order_result(2, OrderStatus.ORDERED)
    actions = LifecycleActions()

    await actions.orders([draft, ordered], READER)
    assert draft.actions == [
        "mark_requested",
        "mark_ordered",
        "cancel",
        "edit",
        "edit_supplier_order_numbers",
        "add_item",
    ]
    assert ordered.actions == ["deliver", "edit_supplier_order_numbers"]

    await actions.orders([ordered], MANAGER)
    assert ordered.actions == [
        "cancel",
        "deliver",
        "edit",
        "edit_supplier_order_numbers",
        "add_item",
    ]


async def test_the_lines_of_an_order_read_their_order_and_a_made_lines_lot():
    result = _order_result(
        1,
        OrderStatus.ORDERED,
        _line(11, OrderItemStatus.PENDING),
        _line(12, OrderItemStatus.ORDERED, line_type=OrderLineType.MADE, lot_id=7),
        _line(13, OrderItemStatus.ORDERED, line_type=OrderLineType.MADE, lot_id=8),
        _line(14, OrderItemStatus.PARTIALLY_DELIVERED, quantity_delivered=4.0),
    )
    lots = _ByIds([_lot(7, LotStatus.CANCELED), _lot(8, LotStatus.IN_PROGRESS)])

    await LifecycleActions(lot_repo=lots).orders([result], MANAGER)

    by_id = {item.id: item.actions for item in result.items}
    assert by_id[11] == [
        "mark_requested",
        "mark_ordered",
        "cancel",
        "edit_quantity",
        "edit",
        "move",
        "remove",
    ]
    # A MADE line on a canceled lot takes no delivery; one on a live lot does.
    assert "deliver" not in by_id[12]
    assert "deliver" in by_id[13]
    assert by_id[14] == [
        "mark_ready_for_pickup",
        "deliver",
        "correct_delivery",
        "close_short",
        "edit",
    ]
    assert lots.calls == [[7, 8]]


async def test_a_line_returned_alone_reads_its_order():
    line = _order_result(1, OrderStatus.CANCELED, _line(11, OrderItemStatus.ORDERED)).items[0]
    orders = _ByIds([_order(1, OrderStatus.CANCELED)])

    await LifecycleActions(order_repo=orders).order_items([line], MANAGER)

    # The order is canceled, so the ordered line takes no delivery.
    assert "deliver" not in line.actions
    assert "cancel" in line.actions
    assert orders.calls == [[1]]


async def test_a_writer_changes_lines_only_until_the_order_is_submitted():
    """Past REQUESTED, changing a line needs manage:orders, as the use cases
    require; a delivery needs receive:deliveries only and stays offered."""
    for status, writer_changes in (
        (OrderStatus.DRAFT, True),
        (OrderStatus.REQUESTED, True),
        (OrderStatus.ORDERED, False),
    ):
        result = _order_result(
            1,
            status,
            _line(11, OrderItemStatus.PENDING),
            _line(12, OrderItemStatus.PARTIALLY_DELIVERED, quantity_delivered=4.0),
        )
        await LifecycleActions().orders([result], READER)
        pending, partial = result.items
        assert ("cancel" in pending.actions) is writer_changes
        assert ("remove" in pending.actions) is writer_changes
        assert ("edit_quantity" in pending.actions) is writer_changes
        assert ("close_short" in partial.actions) is writer_changes
        assert "deliver" in partial.actions

        await LifecycleActions().orders([result], MANAGER)
        pending, partial = result.items
        assert "cancel" in pending.actions
        assert "close_short" in partial.actions


async def test_a_made_line_offers_no_delivery_correction():
    result = _order_result(
        1,
        OrderStatus.ORDERED,
        _line(11, OrderItemStatus.PARTIALLY_DELIVERED, quantity_delivered=4.0),
        _line(
            12,
            OrderItemStatus.PARTIALLY_DELIVERED,
            line_type=OrderLineType.MADE,
            lot_id=7,
            quantity_delivered=4.0,
        ),
    )

    await LifecycleActions(lot_repo=_ByIds([_lot(7, LotStatus.IN_PROGRESS)])).orders(
        [result], MANAGER
    )

    bought, made = result.items
    assert "correct_delivery" in bought.actions
    assert "correct_delivery" not in made.actions
    assert "deliver" in made.actions


async def test_a_line_whose_order_is_gone_offers_nothing():
    line = _order_result(1, OrderStatus.ORDERED, _line(11, OrderItemStatus.ORDERED)).items[0]

    await LifecycleActions(order_repo=_ByIds([])).order_items([line], READER)

    assert line.actions == []


async def test_the_order_response_carries_the_actions():
    result = _order_result(1, OrderStatus.DRAFT, _line(11, OrderItemStatus.PENDING))
    await LifecycleActions().orders([result], READER)

    response = respond(OrderResponse, result)

    assert response.actions == [
        "mark_requested",
        "mark_ordered",
        "cancel",
        "edit",
        "edit_supplier_order_numbers",
        "add_item",
    ]
    assert response.items[0].actions == result.items[0].actions


# ── Lots and positions ──────────────────────────────────────────────────


def _position(position_id: int, kind: LotPositionKind, **values: Any) -> LotPosition:
    values.setdefault("quantity", 5.0)
    values.setdefault("quantity_completed", 0.0)
    values.setdefault("status", LotPositionStatus.PENDING)
    values.setdefault("lot_id", 1)
    values.setdefault("sequence", position_id)
    return make(LotPosition, id=position_id, kind=kind, **values)


async def test_a_lot_and_its_positions_offer_what_their_tables_allow():
    lot = _lot(
        1,
        LotStatus.PLANNED,
        positions=[
            _position(1, LotPositionKind.UNASSIGNED),
            _position(
                2,
                LotPositionKind.EXTERNAL,
                order_item_id=40,
                order_item_status=OrderItemStatus.REQUESTED,
                order_item_quantity=5.0,
            ),
        ],
    )
    result = LotMapper.to_result(lot)

    await LifecycleActions().lots([result], READER)

    assert result.actions == [
        a.value for a in LOT_INTENTS.allowed_actions(result, LotContext(produced=0.0), READER)
    ]
    assert "cancel" not in result.actions
    by_id = {p.id: p.actions for p in result.positions}
    assert by_id[1] == ["assign_external", "assign_internal"]
    assert by_id[2] == ["unassign_external", "record_provision"]
    assert respond(LotResponse, result).positions[1].actions == by_id[2]


async def test_a_manager_may_force_complete_but_not_cancel_a_lot_that_produced_something():
    # A cancel would throw away the good pieces, which force-complete keeps.
    result = LotMapper.to_result(
        _lot(
            1,
            LotStatus.IN_PROGRESS,
            positions=[_position(1, LotPositionKind.INTERNAL, quantity_completed=2.0)],
        )
    )

    await LifecycleActions().lots([result], MANAGER)

    assert "force_complete" in result.actions
    assert "cancel" not in result.actions


async def test_a_manager_may_cancel_a_lot_without_good_pieces():
    result = LotMapper.to_result(
        _lot(1, LotStatus.IN_PROGRESS, positions=[_position(1, LotPositionKind.INTERNAL)])
    )

    await LifecycleActions().lots([result], MANAGER)

    assert "cancel" in result.actions


async def test_positions_of_a_finished_lot_take_no_assignment():
    result = LotMapper.to_result(
        _lot(1, LotStatus.COMPLETED, positions=[_position(1, LotPositionKind.UNASSIGNED)])
    )

    await LifecycleActions().lots([result], MANAGER)

    assert result.actions == []
    assert result.positions[0].actions == []


async def test_a_position_returned_alone_reads_its_lot():
    position = LotMapper.to_result(
        _lot(1, LotStatus.DRAFT, positions=[_position(1, LotPositionKind.UNASSIGNED)])
    ).positions[0]
    assert isinstance(position, LotPositionResult)

    await LifecycleActions(lot_repo=_ByIds([_lot(1, LotStatus.CANCELED)])).positions(
        [position], READER
    )

    assert position.actions == []


async def test_the_lots_list_offers_the_position_actions_on_each_step():
    step = LotSummaryStepResult.model_construct(
        position_id=1,
        position_kind="external",
        position_status="ordered_or_queued",
        position_quantity_remaining=0.0,
    )
    position = LotSummaryPositionResult.model_construct(id=1, order_item_status="pending")
    summary = LotSummaryResult.model_construct(
        status="planned",
        creator_id=1,
        quantity_completed=0.0,
        source_approval_status="pending",
        steps=[step],
        positions=[position],
    )

    await LifecycleActions().lot_summaries([summary], READER)

    assert summary.actions == [
        "hold",
        "scrap",
        "edit_structure",
        "reorder_positions",
        "approve_source",
        "reject_source",
        "switch_source",
    ]
    assert step.actions == ["unassign_external", "record_provision"]


# ── Blocked actions ─────────────────────────────────────────────────────


async def test_an_order_names_the_permission_its_blocked_cancel_needs():
    """Past REQUESTED a writer may not cancel an order. The cancel is still
    possible in its state, so it comes back blocked with manage:orders for
    the client to show disabled, while a manager gets it allowed."""
    ordered = _order_result(1, OrderStatus.ORDERED)
    draft = _order_result(2, OrderStatus.DRAFT)
    delivered = _order_result(3, OrderStatus.DELIVERED)

    await LifecycleActions().orders([ordered, draft, delivered], READER)

    submitted_changes = {
        "cancel": Permission.MANAGE_ORDERS,
        "edit": Permission.MANAGE_ORDERS,
        "add_item": Permission.MANAGE_ORDERS,
    }
    assert ordered.blocked_actions == submitted_changes
    assert "cancel" not in ordered.actions
    assert draft.blocked_actions == {}
    # Nobody can cancel a delivered order, so its cancel is not blocked but
    # absent; its header and a new line still need manage:orders.
    assert delivered.blocked_actions == {
        "edit": Permission.MANAGE_ORDERS,
        "add_item": Permission.MANAGE_ORDERS,
    }

    await LifecycleActions().orders([ordered], MANAGER)
    assert ordered.blocked_actions == {}
    assert "cancel" in ordered.actions


async def test_the_lines_of_a_submitted_order_name_their_blocked_changes():
    result = _order_result(
        1,
        OrderStatus.ORDERED,
        _line(11, OrderItemStatus.ORDERED),
        _line(12, OrderItemStatus.PARTIALLY_DELIVERED, quantity_delivered=4.0),
    )

    await LifecycleActions().orders([result], READER)

    ordered, partial = result.items
    assert ordered.blocked_actions == {
        "mark_ready_for_pickup": Permission.MANAGE_ORDERS,
        "cancel": Permission.MANAGE_ORDERS,
        "edit_quantity": Permission.MANAGE_ORDERS,
        "edit": Permission.MANAGE_ORDERS,
        "move": Permission.MANAGE_ORDERS,
    }
    assert partial.blocked_actions == {
        "mark_ready_for_pickup": Permission.MANAGE_ORDERS,
        "close_short": Permission.MANAGE_ORDERS,
        "edit": Permission.MANAGE_ORDERS,
    }
    # The delivery needs no extra permission and stays allowed.
    assert "deliver" in partial.actions
    assert set(partial.blocked_actions).isdisjoint(partial.actions)


async def test_a_line_returned_alone_names_its_blocked_changes():
    line = _order_result(1, OrderStatus.ORDERED, _line(11, OrderItemStatus.ORDERED)).items[0]

    await LifecycleActions(order_repo=_ByIds([_order(1, OrderStatus.ORDERED)])).order_items(
        [line], READER
    )

    assert line.blocked_actions["cancel"] == Permission.MANAGE_ORDERS


async def test_a_lot_names_the_permission_its_blocked_force_actions_need():
    produced = LotMapper.to_result(
        _lot(
            1,
            LotStatus.IN_PROGRESS,
            positions=[_position(1, LotPositionKind.INTERNAL, quantity_completed=2.0)],
        )
    )
    fresh = LotMapper.to_result(
        _lot(2, LotStatus.IN_PROGRESS, positions=[_position(2, LotPositionKind.INTERNAL)])
    )
    done = LotMapper.to_result(
        _lot(3, LotStatus.COMPLETED, positions=[_position(3, LotPositionKind.INTERNAL)])
    )

    await LifecycleActions().lots([produced, fresh, done], READER)

    # A lot with good pieces cannot be canceled, so only force-complete is
    # blocked; one without them cannot be force-completed.
    assert produced.blocked_actions == {"force_complete": Permission.MANAGE_LOTS}
    assert fresh.blocked_actions == {"cancel": Permission.MANAGE_LOTS}
    assert done.blocked_actions == {}

    await LifecycleActions().lots([produced, fresh], MANAGER)
    assert produced.blocked_actions == {}
    assert fresh.blocked_actions == {}


async def test_the_lots_list_and_the_responses_carry_the_blocked_actions():
    summary = LotSummaryResult.model_construct(
        status="planned",
        creator_id=1,
        quantity_completed=0.0,
        source_approval_status="approved",
        steps=[],
        positions=[],
    )
    await LifecycleActions().lot_summaries([summary], READER)
    assert summary.blocked_actions == {"cancel": Permission.MANAGE_LOTS}

    lot = LotMapper.to_result(
        _lot(1, LotStatus.PLANNED, positions=[_position(1, LotPositionKind.INTERNAL)])
    )
    order = _order_result(1, OrderStatus.ORDERED, _line(11, OrderItemStatus.ORDERED))
    await LifecycleActions().lots([lot], READER)
    await LifecycleActions().orders([order], READER)

    assert respond(LotResponse, lot).blocked_actions == {"cancel": Permission.MANAGE_LOTS}
    order_response = respond(OrderResponse, order)
    assert order_response.blocked_actions == {
        "cancel": Permission.MANAGE_ORDERS,
        "edit": Permission.MANAGE_ORDERS,
        "add_item": Permission.MANAGE_ORDERS,
    }
    assert order_response.items[0].blocked_actions == order.items[0].blocked_actions


# ── Demands ─────────────────────────────────────────────────────────────


def _bought_demand(demand_id: int, status: BoughtItemDemandStatus) -> DemandItemResult:
    return BoughtItemDemandItemMapper.to_result(
        make(BoughtItemDemandItem, id=demand_id, status=status)
    )


async def test_a_demand_is_offered_for_deletion_only_without_allocations():
    free = _bought_demand(1, BoughtItemDemandStatus.OPEN)
    allocated = _bought_demand(2, BoughtItemDemandStatus.ALLOCATED)
    fulfilled = _bought_demand(3, BoughtItemDemandStatus.FULFILLED)
    actions = LifecycleActions(bought_allocations=_Allocations([2, 3]))

    await actions.bought_demands([free, allocated, fulfilled], READER)

    assert free.actions == ["cancel", "fulfil", "allocate", "edit_quantity", "remove"]
    assert allocated.actions == ["cancel", "fulfil", "allocate", "edit_quantity"]
    # A fulfilled demand is neither canceled nor fulfilled again.
    assert fulfilled.actions == []
    assert respond(DemandItemResponse, free).actions == free.actions


async def test_made_and_source_demands_use_their_own_allocations():
    made = MadeItemDemandItemResult.model_construct(id=1, status="canceled")
    source = SourceItemDemandResult.model_construct(id=1, status="open", lot_id=5)

    await LifecycleActions(made_allocations=_Allocations([])).made_demands([made], READER)
    await LifecycleActions(
        source_allocations=_Allocations([1]), lot_repo=_ByIds([_lot(5, LotStatus.PLANNED)])
    ).source_demands([source], READER)

    assert made.actions == ["remove"]
    assert source.actions == ["cancel", "fulfil", "allocate", "edit_quantity"]


async def test_the_raw_material_demand_of_a_started_lot_offers_no_cancel():
    started = make(LotPosition, id=1, lot_id=5, sequence=1, status=LotPositionStatus.IN_PROGRESS)
    held = _lot(5, LotStatus.ON_HOLD, positions=[started])
    source = SourceItemDemandResult.model_construct(id=1, status="allocated", lot_id=5)

    await LifecycleActions(
        source_allocations=_Allocations([1]), lot_repo=_ByIds([held])
    ).source_demands([source], READER)

    assert source.actions == ["fulfil", "allocate", "edit_quantity"]


async def test_results_without_a_user_carry_no_actions():
    """The print resolver and other callers without a reader map results
    without the service; the field then stays empty."""
    result = _order_result(1, OrderStatus.DRAFT, _line(11, OrderItemStatus.PENDING))

    assert result.actions == []
    assert result.items[0].actions == []
    assert isinstance(result.items[0], OrderItemResult)
    assert isinstance(READER, User)
