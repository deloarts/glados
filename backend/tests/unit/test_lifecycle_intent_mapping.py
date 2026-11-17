"""
The lifecycle intents travel from each entity through its application
mapper into the API response, where they are read-only and null until set,
and an interruption carries its reason the same way. The row version stays
out of every response.
"""

import dataclasses
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderItemResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import LotResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ProductionOrderResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandResponse,
)
from src.modules.fulfillment.application.mappers.bought_item_demand_mapper import (
    BoughtItemDemandItemMapper,
)
from src.modules.fulfillment.application.mappers.made_item_demand_mapper import (
    MadeItemDemandItemMapper,
)
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotDemandMapper
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit._entity_enums import enum_fields

CREATED = datetime(2026, 9, 1, 8, tzinfo=UTC)
FIRST = datetime(2026, 9, 2, 9, tzinfo=UTC)
SECOND = datetime(2026, 9, 3, 10, tzinfo=UTC)
THIRD = datetime(2026, 9, 4, 11, tzinfo=UTC)

_NEUTRAL: dict[str, Callable[[], object]] = {
    "datetime": lambda: CREATED,
    "date": lambda: CREATED.date(),
    "str": lambda: "x",
    "float": lambda: 1.0,
    "int": lambda: 1,
    "bool": lambda: False,
    "list": list,
    "dict": dict,
}


def make[T](cls: type[T], **values: Any) -> T:
    """Builds an entity, filling every required field the caller did not
    pass with a neutral value of its annotated type (None where the type
    allows it, the first member for an enum)."""
    enums = enum_fields(cls)
    for f in dataclasses.fields(cls):  # type: ignore[arg-type]
        if f.name in values or not f.init:
            continue
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:
            continue
        if "None" in str(f.type):
            values[f.name] = None
            continue
        if f.name in enums:
            values[f.name] = next(iter(enums[f.name]))
            continue
        type_name = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", "")
        values[f.name] = _NEUTRAL[type_name.split("[")[0]]()
    return cls(**values)


def respond[R: BaseModel](response_cls: type[R], result: BaseModel) -> R:
    """Validates a mapper result into its response the way FastAPI validates
    a route's return value against the route's response model."""
    return response_cls.model_validate(result, from_attributes=True)


def _json(response: BaseModel) -> dict[str, Any]:
    return response.model_dump(mode="json")


# ── Supplier orders and their lines ──────────────────────────────────


def _order(**intents: Any) -> Order:
    return make(Order, status=OrderStatus.REQUESTED, **intents)


def _order_item(**intents: Any) -> OrderItem:
    return make(
        OrderItem, status=OrderItemStatus.CANCELED, line_type=OrderLineType.BOUGHT, **intents
    )


def test_order_result_carries_the_intents() -> None:
    result = OrderMapper.to_result(
        _order(requested_at=FIRST, canceled_at=SECOND), items=[_order_item(requested_at=THIRD)]
    )

    assert (result.requested_at, result.canceled_at) == (FIRST, SECOND)
    assert (result.items[0].requested_at, result.items[0].canceled_at) == (THIRD, None)


def test_order_item_result_carries_the_intents() -> None:
    result = OrderItemMapper.to_result(_order_item(requested_at=FIRST, canceled_at=SECOND))

    assert (result.requested_at, result.canceled_at) == (FIRST, SECOND)


def test_order_response_shows_the_intents() -> None:
    response = respond(
        OrderResponse,
        OrderMapper.to_result(_order(requested_at=FIRST), items=[_order_item(canceled_at=SECOND)]),
    )

    assert (response.requested_at, response.canceled_at) == (FIRST, None)
    assert (response.items[0].requested_at, response.items[0].canceled_at) == (None, SECOND)
    body = _json(response)
    assert body["canceled_at"] is None
    assert body["items"][0]["canceled_at"] is not None


def test_order_item_response_shows_the_intents() -> None:
    response = respond(OrderItemResponse, OrderItemMapper.to_result(_order_item()))

    assert (response.requested_at, response.canceled_at) == (None, None)
    assert {"requested_at", "canceled_at"} <= _json(response).keys()


# ── Lots and production orders ───────────────────────────────────────


def test_lot_result_and_response_carry_the_intents() -> None:
    lot = make(
        ProductionLot,
        status=LotStatus.COMPLETED,
        priority=UrgencyClass.NORMAL,
        held_at=FIRST,
        force_completed_at=SECOND,
    )

    result = LotMapper.to_result(lot)
    response = respond(LotResponse, result)

    assert (result.held_at, result.canceled_at, result.force_completed_at) == (FIRST, None, SECOND)
    assert (response.held_at, response.canceled_at, response.force_completed_at) == (
        FIRST,
        None,
        SECOND,
    )
    assert {"held_at", "canceled_at", "force_completed_at"} <= _json(response).keys()


def test_production_order_result_and_response_carry_the_intent_and_reasons() -> None:
    def interruption(**values: Any) -> ProductionOrderInterruption:
        return make(
            ProductionOrderInterruption,
            production_order_id=1,
            paused_at=FIRST,
            resumed_at=None,
            resumed_by_id=None,
            **values,
        )

    order = make(
        ProductionOrder,
        status=ProductionOrderStatus.CANCELED,
        priority=UrgencyClass.NORMAL,
        canceled_at=THIRD,
        interruptions=[interruption(), interruption(reason=InterruptionReason.LOT_HOLD)],
    )

    result = ProductionOrderMapper.to_result(order)
    response = respond(ProductionOrderResponse, result)

    assert result.canceled_at == THIRD
    assert [i.reason for i in result.interruptions] == ["manual", "lot_hold"]
    assert response.canceled_at == THIRD
    assert [i.reason for i in response.interruptions] == [
        InterruptionReason.MANUAL,
        InterruptionReason.LOT_HOLD,
    ]
    assert [i["reason"] for i in _json(response)["interruptions"]] == ["manual", "lot_hold"]


# ── Demands ───────────────────────────────────────────────────────────


def test_bought_demand_result_and_response_carry_the_intents() -> None:
    demand = make(BoughtItemDemandItem, status=BoughtItemDemandStatus.CANCELED, canceled_at=FIRST)

    response = respond(DemandItemResponse, BoughtItemDemandItemMapper.to_result(demand))

    assert (response.canceled_at, response.fulfilled_manually_at) == (FIRST, None)


def test_made_demand_result_and_response_carry_the_intents() -> None:
    demand = make(
        MadeItemDemandItem, status=MadeItemDemandStatus.FULFILLED, fulfilled_manually_at=SECOND
    )

    response = respond(MadeItemDemandResponse, MadeItemDemandItemMapper.to_result(demand))
    lot_view = respond(LotDemandResponse, LotDemandMapper.to_result(demand, 2.0))

    assert (response.canceled_at, response.fulfilled_manually_at) == (None, SECOND)
    assert (lot_view.canceled_at, lot_view.fulfilled_manually_at) == (None, SECOND)


def test_source_demand_result_and_response_carry_the_intents() -> None:
    demand = make(
        SourceItemDemandItem,
        status=SourceItemDemandStatus.CANCELED,
        canceled_at=FIRST,
        fulfilled_manually_at=None,
    )

    response = respond(SourceItemDemandResponse, SourceItemDemandMapper.to_result(demand))

    assert (response.canceled_at, response.fulfilled_manually_at) == (FIRST, None)


# ── What the responses leave out ─────────────────────────────────────


def test_no_response_exposes_the_row_version() -> None:
    responses: list[type[BaseModel]] = [
        OrderResponse,
        OrderItemResponse,
        LotResponse,
        ProductionOrderResponse,
        DemandItemResponse,
        MadeItemDemandResponse,
        SourceItemDemandResponse,
    ]
    assert [cls.__name__ for cls in responses if "version" in cls.model_fields] == []
