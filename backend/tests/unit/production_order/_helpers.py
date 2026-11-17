"""
Plain factory functions building minimal valid entities for the
production_order test modules.

A production order's status is derived from its facts by the lifecycle
reconciler, so an order built in a status carries the facts that status
stands for (give_status_facts); otherwise the first use case that touches
it would store a different status.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


def make_fabrication_method(id: int = 1) -> FabricationMethod:
    return FabricationMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": f"Method {id}"}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
    )


def make_machine(
    id: int = 1,
    fabrication_method_ids: list[int] | None = None,
    is_qa_machine: bool = False,
) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        internal_name=f"Machine {id}",
        vendor="Contoso",
        model="VF-2",
        fabrication_method_ids=fabrication_method_ids
        if fabrication_method_ids is not None
        else [1],
        max_part_dimension=None,
        note=None,
        creator_id=1,
        is_qa_machine=is_qa_machine,
    )


def make_step(
    id: int = 1,
    position_id: int = 1,
    fabrication_method_id: int | None = 1,
    estimated_setup_minutes: int | None = 10,
    estimated_minutes_per_piece: float | None = 2.0,
    fabrication_method_requires_machine: bool = True,
    fabrication_method_required_external: bool = False,
    fabrication_method_default_supplier_id: int | None = None,
    role: StepRole = StepRole.FABRICATION,
    inspection_method_id: int | None = None,
    inspection_method_name: str | None = None,
    inspection_method_requires_evidence: bool | None = None,
) -> LotStep:
    return LotStep(
        id=id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=estimated_setup_minutes,
        estimated_minutes_per_piece=estimated_minutes_per_piece,
        sequence=1,
        creator_id=1,
        fabrication_method_id=fabrication_method_id,
        lot_id=1,
        position_id=position_id,
        source_process_id=None,
        fabrication_method_name=(
            LocalizedText({"enGB": f"Method {fabrication_method_id}"})
            if fabrication_method_id
            else LocalizedText()
        ),
        fabrication_method_requires_machine=fabrication_method_requires_machine,
        fabrication_method_required_external=fabrication_method_required_external,
        fabrication_method_default_supplier_id=fabrication_method_default_supplier_id,
        role=role,
        inspection_method_id=inspection_method_id,
        inspection_method_name=(
            LocalizedText({"enGB": inspection_method_name})
            if inspection_method_name is not None
            else None
        ),
        inspection_method_requires_evidence=inspection_method_requires_evidence,
    )


def make_position(
    id: int = 1,
    lot_id: int = 1,
    sequence: int = 1,
    kind: LotPositionKind = LotPositionKind.UNASSIGNED,
    status: LotPositionStatus = LotPositionStatus.PENDING,
    quantity: float = 10.0,
    quantity_completed: float = 0.0,
    steps: list[LotStep] | None = None,
) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=status,
        quantity=quantity,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=lot_id,
        steps=steps if steps is not None else [make_step(position_id=id)],
    )


def make_lot(
    id: int = 1,
    status: LotStatus = LotStatus.PARTIALLY_PLANNED,
    quantity: float = 10.0,
    positions: list[LotPosition] | None = None,
    input_demand_id: int | None = None,
) -> ProductionLot:
    return ProductionLot(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number=f"LOT-{id:04d}",
        quantity=quantity,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=input_demand_id,
        positions=positions if positions is not None else [],
    )


# When a seeded order started, paused, ended or was canceled.
SEEDED_START = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
SEEDED_PAUSE = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
SEEDED_END = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

_seeded_row_ids = itertools.count(9001)


def give_status_facts(
    order: ProductionOrder, interruption_reason: InterruptionReason = InterruptionReason.MANUAL
) -> ProductionOrder:
    """Gives an order the facts its stored status stands for: a started
    order its actual_start, a paused one an open interruption of
    `interruption_reason`, a completed one a completion row of its quantity
    and its actual_end, a canceled one its canceled_at."""
    status = order.status
    if status in (
        ProductionOrderStatus.IN_PROGRESS.value,
        ProductionOrderStatus.PAUSED.value,
        ProductionOrderStatus.COMPLETED.value,
    ):
        order.actual_start = order.actual_start or SEEDED_START
    if status == ProductionOrderStatus.PAUSED.value and not any(
        i.resumed_at is None for i in order.interruptions
    ):
        order.interruptions = [
            *order.interruptions,
            ProductionOrderInterruption(
                id=next(_seeded_row_ids),
                production_order_id=order.id,
                paused_at=SEEDED_PAUSE,
                resumed_at=None,
                paused_by_id=1,
                resumed_by_id=None,
                created=SEEDED_PAUSE,
                reason=interruption_reason,
            ),
        ]
    if status == ProductionOrderStatus.COMPLETED.value:
        order.actual_end = order.actual_end or SEEDED_END
        if sum(c.quantity for c in order.completions) < order.quantity:
            order.completions = [
                *order.completions,
                ProductionOrderCompletion(
                    id=next(_seeded_row_ids),
                    production_order_id=order.id,
                    quantity=order.quantity,
                    quantity_accepted=order.quantity_completed,
                    quantity_rejected=order.quantity - order.quantity_completed,
                    completion_date=SEEDED_END.date(),
                    note=None,
                    operator_id=1,
                    recorded_by_id=1,
                    created=SEEDED_END,
                ),
            ]
    if status == ProductionOrderStatus.CANCELED.value:
        order.canceled_at = order.canceled_at or SEEDED_END
    return order


def make_order(
    id: int = 1,
    machine_id: int | None = 1,
    machine_pool_id: int | None = None,
    lot_position_id: int = 1,
    status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
    quantity: float = 10.0,
    quantity_completed: float = 0.0,
    queue_sequence: int = 1,
    pinned: bool = False,
    interruption_reason: InterruptionReason = InterruptionReason.MANUAL,
) -> ProductionOrder:
    """An order in `status`, with the facts of that status (see
    give_status_facts)."""
    order = ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=pinned,
        queue_sequence=queue_sequence,
        quantity=quantity,
        quantity_completed=quantity_completed,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=machine_id,
        machine_pool_id=machine_pool_id,
        lot_position_id=lot_position_id,
    )
    return give_status_facts(order, interruption_reason)


def make_pool(
    id: int = 1,
    machine_ids: list[int] | None = None,
    machines: list[ProductionMachine] | None = None,
) -> MachinePool:
    return MachinePool(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name=f"Pool {id}",
        machine_ids=machine_ids if machine_ids is not None else [1, 2],
        note=None,
        creator_id=1,
        machines=machines if machines is not None else [],
    )
