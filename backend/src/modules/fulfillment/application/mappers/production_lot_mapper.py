"""Converts between ProductionLot/LotPosition/LotStep/LotEvent domain entities and DTOs,
including summary and detailed views."""

from datetime import date
from typing import Literal

from src.modules.fulfillment.application.dto.production_lot_dto import FollowUpLotResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotEventResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionOrderLineResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionProvisionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotStepResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import (
    LotSummaryProductionOrderResult,
)
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryStepResult
from src.modules.fulfillment.application.mappers.made_item_demand_mapper import (
    MadeItemDemandItemMapper,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.lot_rules import lot_position_remaining
from src.modules.fulfillment.domain.services.scheduling import EarliestStartExplanation
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.application.mappers.user_mapper import UserMapper

# (date, source, demand_item_id) per lot, see
# _context.describe_lot_target_dates.
TargetDateEntry = tuple[date | None, Literal["lot", "demand"] | None, int | None]


class LotStepMapper:
    @staticmethod
    def to_result(entity: LotStep) -> LotStepResult:
        return LotStepResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            note=entity.note,
            estimated_setup_minutes=entity.estimated_setup_minutes,
            estimated_minutes_per_piece=entity.estimated_minutes_per_piece,
            sequence=entity.sequence,
            creator_id=entity.creator_id,
            role=entity.role,
            inspection_method_id=entity.inspection_method_id,
            fabrication_method_id=entity.fabrication_method_id,
            fabrication_method_name=entity.fabrication_method_name.as_dict(),
            fabrication_method_requires_machine=entity.fabrication_method_requires_machine,
            fabrication_method_required_external=entity.fabrication_method_required_external,
            fabrication_method_default_supplier_id=entity.fabrication_method_default_supplier_id,
            inspection_method_name=(
                entity.inspection_method_name.as_dict() if entity.inspection_method_name else None
            ),
            inspection_method_requires_evidence=entity.inspection_method_requires_evidence,
            lot_id=entity.lot_id,
            position_id=entity.position_id,
            source_process_id=entity.source_process_id,
            time_budget_per_piece=entity.time_budget_per_piece,
        )


class LotPositionMapper:
    @staticmethod
    def to_result(
        entity: LotPosition, conflicts_by_order_id: dict[int, list[str]] | None = None
    ) -> LotPositionResult:
        return LotPositionResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            sequence=entity.sequence,
            kind=entity.kind,
            status=entity.status,
            quantity=entity.quantity,
            quantity_completed=entity.quantity_completed,
            quantity_remaining=lot_position_remaining(entity),
            note=entity.note,
            creator_id=entity.creator_id,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            lot_id=entity.lot_id,
            steps=[LotStepMapper.to_result(s) for s in entity.steps],
            order_item_id=entity.order_item_id,
            order_id=entity.order_id,
            order_number=entity.order_number,
            supplier_name=entity.supplier_name,
            order_item_status=_value_or_empty(entity.order_item_status),
            order_item_closed_short=entity.order_item_closed_short,
            earlier_order_lines=[
                LotPositionOrderLineResult(
                    order_item_id=line.order_item_id,
                    order_id=line.order_id,
                    order_number=line.order_number,
                    supplier_name=line.supplier_name,
                    quantity=line.quantity,
                    quantity_delivered=line.quantity_delivered,
                    unit=line.unit,
                    closed_short=line.closed_short,
                )
                for line in entity.earlier_order_lines
            ],
            expected_delivery_date=entity.expected_delivery_date,
            planned_pickup_date=entity.planned_pickup_date,
            planned_delivery_date=entity.planned_delivery_date,
            production_orders=[
                ProductionOrderMapper.to_result(
                    o, conflicts=(conflicts_by_order_id or {}).get(o.id, [])
                )
                for o in entity.production_orders
            ],
        )


class LotPositionProvisionMapper:
    @staticmethod
    def to_result(entity: LotPositionProvision) -> LotPositionProvisionResult:
        return LotPositionProvisionResult(
            id=entity.id,
            public_id=entity.public_id,
            lot_position_id=entity.lot_position_id,
            quantity=entity.quantity,
            provision_date=entity.provision_date,
            note=entity.note,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            created=entity.created,
        )


def _replacement_lot_ids(entity: ProductionLot) -> list[int]:
    """ids of entity.follow_up_lots whose disposition is "replacement";
    follow_up_lots is already batched for both single-lot and list reads
    (see _enrich_lots_with_lineage_info), so this costs no extra query."""
    return [
        f.id for f in entity.follow_up_lots if f.disposition == LotOriginDisposition.REPLACEMENT
    ]


def _to_summary_step(
    step: LotStep, positions_by_id: dict[int, LotPosition]
) -> LotSummaryStepResult:
    """One step's summary row, with a handful of fields denormalized from
    its own position (kind/status/quantity) so the frontend never has to
    cross-reference the position list itself just to render a step."""
    position = positions_by_id.get(step.position_id)
    position_kind = position.kind if position else LotPositionKind.UNASSIGNED
    position_status = position.status if position else LotPositionStatus.default()
    position_needs_machine = position is not None and (
        position.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
        and any(o.machine_id is None for o in position.production_orders)
    )
    position_quantity = position.quantity if position else 0.0
    position_quantity_remaining = lot_position_remaining(position) if position else 0.0
    return LotSummaryStepResult(
        id=step.id,
        public_id=step.public_id,
        created=step.created,
        note=step.note,
        estimated_setup_minutes=step.estimated_setup_minutes,
        estimated_minutes_per_piece=step.estimated_minutes_per_piece,
        time_budget_per_piece=step.time_budget_per_piece,
        sequence=step.sequence,
        creator_id=step.creator_id,
        role=step.role,
        inspection_method_id=step.inspection_method_id,
        fabrication_method_id=step.fabrication_method_id,
        fabrication_method_name=step.fabrication_method_name.as_dict(),
        fabrication_method_requires_machine=step.fabrication_method_requires_machine,
        fabrication_method_required_external=step.fabrication_method_required_external,
        fabrication_method_default_supplier_id=step.fabrication_method_default_supplier_id,
        inspection_method_name=(
            step.inspection_method_name.as_dict() if step.inspection_method_name else None
        ),
        inspection_method_requires_evidence=step.inspection_method_requires_evidence,
        lot_id=step.lot_id,
        position_id=step.position_id,
        source_process_id=step.source_process_id,
        position_kind=position_kind,
        position_needs_machine=position_needs_machine,
        position_status=position_status,
        position_quantity=position_quantity,
        position_quantity_remaining=position_quantity_remaining,
    )


def _to_summary_production_order(
    o: ProductionOrder,
    conflicts_by_order_id: dict[int, list[str]] | None,
    explanations_by_order_id: dict[int, EarliestStartExplanation] | None,
) -> LotSummaryProductionOrderResult:
    explanation = (explanations_by_order_id or {}).get(o.id)
    return LotSummaryProductionOrderResult(
        id=o.id,
        status=o.status,
        machine_id=o.machine_id,
        machine_internal_name=o.machine_internal_name,
        machine_pool_id=o.machine_pool_id,
        machine_pool_name=o.machine_pool_name,
        planned_start=o.planned_start,
        planned_end=o.planned_end,
        actual_start=o.actual_start,
        actual_end=o.actual_end,
        quantity_completed=o.quantity_completed,
        edit_version=o.edit_version,
        planned_by_name=o.planned_by.full_name if o.planned_by else None,
        conflicts=(conflicts_by_order_id or {}).get(o.id, []),
        earliest_start_reason=explanation.reason if explanation else None,
        earliest_start_date=explanation.date if explanation else None,
    )


def _to_summary_position(
    position: LotPosition,
    lead_days_by_position_id: dict[int, tuple[int, str]] | None,
    conflicts_by_order_id: dict[int, list[str]] | None,
    explanations_by_order_id: dict[int, EarliestStartExplanation] | None,
) -> LotSummaryPositionResult:
    lead_days_entry = (lead_days_by_position_id or {}).get(position.id)
    lead_days = lead_days_entry[0] if lead_days_entry is not None else None
    lead_days_source = lead_days_entry[1] if lead_days_entry is not None else None
    return LotSummaryPositionResult(
        id=position.id,
        kind=position.kind,
        order_id=position.order_id,
        order_number=position.order_number,
        order_item_id=position.order_item_id,
        order_item_status=_value_or_empty(position.order_item_status),
        order_item_closed_short=position.order_item_closed_short,
        order_item_quantity=position.order_item_quantity,
        order_item_quantity_delivered=position.order_item_quantity_delivered,
        order_item_unit=position.order_item_unit,
        order_item_items_per_unit=position.order_item_items_per_unit,
        order_item_edit_version=position.order_item_edit_version,
        expected_delivery_date=position.expected_delivery_date,
        delivery_date=position.order_item_delivery_date,
        expected_pickup_date=position.order_item_expected_pickup_date,
        ready_for_pickup_date=position.order_item_ready_for_pickup_date,
        delivery_record_count=position.order_item_delivery_record_count,
        ordered_by_name=position.order_item_ordered_by_name,
        planned_pickup_date=position.planned_pickup_date,
        planned_delivery_date=position.planned_delivery_date,
        lead_days=lead_days,
        lead_days_source=lead_days_source,
        production_orders=[
            _to_summary_production_order(o, conflicts_by_order_id, explanations_by_order_id)
            for o in position.production_orders
        ],
    )


class LotMapper:
    @staticmethod
    def to_result(
        entity: ProductionLot, conflicts_by_order_id: dict[int, list[str]] | None = None
    ) -> LotResult:
        return LotResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            lot_number=entity.lot_number,
            quantity=entity.quantity,
            quantity_completed=entity.quantity_completed,
            status=entity.status,
            priority=entity.priority,
            note=entity.note,
            required_delivery_date=entity.required_delivery_date,
            completed_at=entity.completed_at,
            quantity_scrapped=entity.quantity_scrapped,
            held_at=entity.held_at,
            canceled_at=entity.canceled_at,
            edit_version=entity.edit_version,
            force_completed_at=entity.force_completed_at,
            replacement_lot_ids=_replacement_lot_ids(entity),
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            made_item_id=entity.made_item_id,
            made_item_part_number=entity.made_item_part_number,
            made_item_article_name=entity.made_item_article_name,
            made_item_revision=entity.made_item_revision,
            made_item_material=entity.made_item_material,
            made_item_public_id=entity.made_item_public_id,
            source_bought_item_id=entity.source_bought_item_id,
            source_item_id=entity.source_item_id,
            source_made_item_id=entity.source_made_item_id,
            source_label=entity.source_label,
            source_sublabel=entity.source_sublabel,
            source_order_id=entity.source_order_id,
            source_order_number=entity.source_order_number,
            source_expected_delivery_date=entity.source_expected_delivery_date,
            source_delivery_date=entity.source_delivery_date,
            demand_status=_value_or_empty(entity.demand_status),
            is_alteration=entity.is_alteration,
            project_id=entity.project_id,
            project_number=entity.project_number,
            project_customer=entity.project_customer,
            product_id=entity.product_id,
            product_number=entity.product_number,
            input_demand_id=entity.input_demand_id,
            origin_lot_id=entity.origin_lot_id,
            origin_lot_number=entity.origin_lot_number or None,
            origin_disposition=entity.origin_disposition,
            source_approval_status=entity.source_approval_status,
            source_approved_by_id=entity.source_approved_by_id,
            source_approved_date=entity.source_approved_date,
            source_rejected_by_id=entity.source_rejected_by_id,
            source_rejected_date=entity.source_rejected_date,
            source_rejection_reason=entity.source_rejection_reason,
            follow_up_lots=[
                FollowUpLotResult(
                    id=f.id, lot_number=f.lot_number, disposition=f.disposition, quantity=f.quantity
                )
                for f in entity.follow_up_lots
            ],
            positions=[
                LotPositionMapper.to_result(p, conflicts_by_order_id) for p in entity.positions
            ],
            steps=[LotStepMapper.to_result(s) for s in entity.steps],
        )

    @staticmethod
    def to_summary(
        entity: ProductionLot,
        conflicts_by_order_id: dict[int, list[str]] | None = None,
        explanations_by_order_id: dict[int, EarliestStartExplanation] | None = None,
        lead_days_by_position_id: dict[int, tuple[int, str]] | None = None,
        target_date_by_lot_id: dict[int, TargetDateEntry] | None = None,
    ) -> LotSummaryResult:
        positions_by_id = {p.id: p for p in entity.positions}

        target_date_entry = (target_date_by_lot_id or {}).get(entity.id)
        target_date = target_date_entry[0] if target_date_entry is not None else None
        target_date_source = target_date_entry[1] if target_date_entry is not None else None
        target_date_demand_item_id = target_date_entry[2] if target_date_entry is not None else None

        return LotSummaryResult(
            id=entity.id,
            public_id=entity.public_id,
            lot_number=entity.lot_number,
            quantity=entity.quantity,
            quantity_completed=entity.quantity_completed,
            status=entity.status,
            priority=entity.priority,
            created=entity.created,
            changed=entity.changed,
            required_delivery_date=entity.required_delivery_date,
            completed_at=entity.completed_at,
            quantity_scrapped=entity.quantity_scrapped,
            replacement_lot_ids=_replacement_lot_ids(entity),
            edit_version=entity.edit_version,
            target_date=target_date,
            target_date_source=target_date_source,
            target_date_demand_item_id=target_date_demand_item_id,
            made_item_id=entity.made_item_id,
            made_item_part_number=entity.made_item_part_number,
            made_item_article_name=entity.made_item_article_name,
            made_item_revision=entity.made_item_revision,
            made_item_material=entity.made_item_material,
            source_bought_item_id=entity.source_bought_item_id,
            source_item_id=entity.source_item_id,
            source_made_item_id=entity.source_made_item_id,
            source_label=entity.source_label,
            source_sublabel=entity.source_sublabel,
            source_material=entity.source_material,
            source_order_id=entity.source_order_id,
            source_order_number=entity.source_order_number,
            source_expected_delivery_date=entity.source_expected_delivery_date,
            source_delivery_date=entity.source_delivery_date,
            demand_status=_value_or_empty(entity.demand_status),
            is_alteration=entity.is_alteration,
            project_id=entity.project_id,
            project_number=entity.project_number,
            project_customer=entity.project_customer,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            input_demand_id=entity.input_demand_id,
            origin_lot_id=entity.origin_lot_id,
            origin_disposition=entity.origin_disposition,
            source_approval_status=entity.source_approval_status,
            source_approved_by_id=entity.source_approved_by_id,
            source_approved_date=entity.source_approved_date,
            source_rejected_by_id=entity.source_rejected_by_id,
            source_rejected_date=entity.source_rejected_date,
            source_rejection_reason=entity.source_rejection_reason,
            steps=[_to_summary_step(s, positions_by_id) for s in entity.steps],
            positions=[
                _to_summary_position(
                    p, lead_days_by_position_id, conflicts_by_order_id, explanations_by_order_id
                )
                for p in entity.positions
            ],
        )


class LotEventMapper:
    @staticmethod
    def to_result(entity: LotEvent) -> LotEventResult:
        return LotEventResult(
            id=entity.id,
            public_id=entity.public_id,
            lot_id=entity.lot_id,
            occurred_at=entity.occurred_at,
            actor_id=entity.actor_id,
            actor_username=entity.actor_username,
            actor_full_name=entity.actor_full_name,
            event_type=entity.event_type.value,
            entity=entity.entity,
            entity_id=entity.entity_id,
            summary=entity.summary,
            payload=entity.payload,
        )


class LotDemandMapper:
    @staticmethod
    def to_result(demand: MadeItemDemandItem, allocated_quantity: float) -> LotDemandResult:
        return LotDemandResult(
            **MadeItemDemandItemMapper.to_result(demand).model_dump(),
            allocated_quantity=allocated_quantity,
        )


def _value_or_empty(status: OrderItemStatus | SourceItemDemandStatus | None) -> str:
    """A status the result carries as a string, empty when there is none."""
    return status.value if status is not None else ""
