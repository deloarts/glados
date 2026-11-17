"""Converts between ProductionOrder/ProductionOrderCompletion/ManufacturingAssessment domain
entities and DTOs."""

from src.modules.fulfillment.application.dto.production_order_dto import (
    ManufacturingAssessmentResult,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ProductionOrderCompletionResult,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ProductionOrderInterruptionResult,
)
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.platform.application.mappers.user_mapper import UserMapper


class ProductionOrderCompletionMapper:
    @staticmethod
    def to_result(entity: ProductionOrderCompletion) -> ProductionOrderCompletionResult:
        return ProductionOrderCompletionResult(
            id=entity.id,
            public_id=entity.public_id,
            production_order_id=entity.production_order_id,
            quantity=entity.quantity,
            quantity_accepted=entity.quantity_accepted,
            quantity_rejected=entity.quantity_rejected,
            quantity_rework=entity.quantity_rework,
            quantity_scrap=entity.quantity_scrap,
            scrap_reason=entity.scrap_reason,
            reject_reason=entity.reject_reason,
            completion_date=entity.completion_date,
            note=entity.note,
            operator_id=entity.operator_id,
            operator=UserMapper.to_public_result(entity.operator) if entity.operator else None,
            recorded_by_id=entity.recorded_by_id,
            recorded_by=(
                UserMapper.to_public_result(entity.recorded_by) if entity.recorded_by else None
            ),
            created=entity.created,
            reverses_completion_id=entity.reverses_completion_id,
            machine_id=entity.machine_id,
        )


class ProductionOrderMapper:
    @staticmethod
    def to_result(
        entity: ProductionOrder, conflicts: list[str] | None = None
    ) -> ProductionOrderResult:
        return ProductionOrderResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            production_order_number=entity.production_order_number,
            status=entity.status,
            priority=entity.priority,
            pinned=entity.pinned,
            queue_sequence=entity.queue_sequence,
            quantity=entity.quantity,
            quantity_completed=entity.quantity_completed,
            quantity_processed=entity.pieces_processed,
            quantity_open=max(entity.quantity - entity.pieces_processed, 0.0),
            estimated_duration_minutes=entity.estimated_duration_minutes,
            note=entity.note,
            planned_start=entity.planned_start,
            planned_end=entity.planned_end,
            not_before=entity.not_before,
            actual_start=entity.actual_start,
            actual_end=entity.actual_end,
            canceled_at=entity.canceled_at,
            edit_version=entity.edit_version,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            planned_by_id=entity.planned_by_id,
            planned_by=(
                UserMapper.to_public_result(entity.planned_by) if entity.planned_by else None
            ),
            started_operator_id=entity.started_operator_id,
            started_operator=(
                UserMapper.to_public_result(entity.started_operator)
                if entity.started_operator
                else None
            ),
            planned_end_at_start=entity.planned_end_at_start,
            machine_id=entity.machine_id,
            machine_internal_name=entity.machine_internal_name,
            machine_pool_id=entity.machine_pool_id,
            machine_pool_name=entity.machine_pool_name,
            lot_position_id=entity.lot_position_id,
            lot_id=entity.lot_id,
            lot_number=entity.lot_number,
            lot_public_id=entity.lot_public_id,
            made_item_public_id=entity.made_item_public_id,
            project_id=entity.project_id,
            project_number=entity.project_number,
            product_id=entity.product_id,
            product_number=entity.product_number,
            made_item_part_number=entity.made_item_part_number,
            made_item_id=entity.made_item_id,
            made_item_revision=entity.made_item_revision,
            made_item_article_name=entity.made_item_article_name,
            made_item_material=entity.made_item_material,
            made_item_mass=entity.made_item_mass,
            made_item_base_size=entity.made_item_base_size,
            lot_position_sequence=entity.lot_position_sequence,
            lot_position_count=entity.lot_position_count,
            completions=[ProductionOrderCompletionMapper.to_result(c) for c in entity.completions],
            interruptions=[
                ProductionOrderInterruptionResult(
                    paused_at=i.paused_at,
                    resumed_at=i.resumed_at,
                    reason=i.reason,
                    paused_operator_id=i.paused_operator_id,
                )
                for i in entity.interruptions
            ],
            waiting_on_raw_material=entity.waiting_on_raw_material,
            can_start=entity.can_start,
            actions=list(entity.actions),
            conflicts=conflicts or [],
            assessment=(
                ManufacturingAssessmentMapper.to_result(entity.assessment)
                if entity.assessment
                else None
            ),
        )


class ManufacturingAssessmentMapper:
    @staticmethod
    def to_result(entity: ManufacturingAssessment) -> ManufacturingAssessmentResult:
        return ManufacturingAssessmentResult(
            id=entity.id,
            public_id=entity.public_id,
            production_order_id=entity.production_order_id,
            operator_id=entity.operator_id,
            operator=UserMapper.to_public_result(entity.operator) if entity.operator else None,
            actual_minutes_per_piece=entity.actual_minutes_per_piece,
            actual_setup_minutes=entity.actual_setup_minutes,
            complexity=entity.complexity,
            note=entity.note,
            created=entity.created,
        )
