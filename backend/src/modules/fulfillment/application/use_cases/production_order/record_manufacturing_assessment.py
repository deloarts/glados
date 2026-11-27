"""
Post-manufacturing assessment prompted at a ProductionOrder's final
completion, training dataset for future AI-assisted time estimation.
A completed order has one active assessment. A second one is refused,
unless a reversal took a completion back after the active one was recorded:
then the order went to work again, and the new assessment describes the run
that finished it. The earlier one is marked superseded and kept, never
edited (manufacturing_assessment_rules.py).
"""

from src.modules.fulfillment.application.dto.production_order_dto import (
    ManufacturingAssessmentResult,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordManufacturingAssessmentCommand,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ManufacturingAssessmentMapper,
)
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.errors import ManufacturingAssessmentAlreadyExistsError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.services.manufacturing_assessment_rules import (
    is_assessment_replaceable,
)
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.manufacturing_assessment_repository import (
    IManufacturingAssessmentRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class RecordManufacturingAssessment:
    def __init__(
        self,
        assessment_repo: IManufacturingAssessmentRepository,
        order_repo: IProductionOrderRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._assessments = assessment_repo
        self._orders = order_repo
        # No ManufacturingAssessmentRecorded event exists (nothing downstream
        # subscribes yet, this is groundwork for future time estimation, not
        # a notification-worthy occurrence). event_bus is still accepted for
        # constructor-shape consistency with sibling production-order use
        # cases, matching precedent even though unused here.
        self._bus = event_bus
        self._uow = uow

    async def execute(
        self,
        actor: User,
        production_order_id: int,
        cmd: RecordManufacturingAssessmentCommand,
    ) -> ManufacturingAssessmentResult:
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        # Recording an assessment edits the production order's record, so it
        # takes the same gate its sibling mutations use (start/pause/cancel/
        # complete), not merely an active session.
        ProductionOrderRules.assert_can_update(actor, order)
        if order.status != ProductionOrderStatus.COMPLETED:
            raise ProductionOrderInvalidStatusTransitionError(
                f"Production order #{order.id} is {order.status.value!r}; assessments can only be "
                f"recorded for completed orders."
            )
        now = now_utc()
        active = await self._assessments.get_by_production_order_id(production_order_id)
        if active is not None:
            if not is_assessment_replaceable(active, order.completions):
                raise ManufacturingAssessmentAlreadyExistsError(
                    f"Production order #{production_order_id} already has a manufacturing "
                    "assessment."
                )
            await self._assessments.mark_superseded(active.id, now)

        # RecordManufacturingAssessmentCommand has no operator_id field,
        # unlike start/pause, there's no shared-account ambiguity to
        # disambiguate here, so the assessing operator is always the actor
        # recording the assessment.
        operator_id = actor.id

        saved = await self._assessments.save(
            ManufacturingAssessment(
                id=0,
                production_order_id=production_order_id,
                operator_id=operator_id,
                actual_minutes_per_piece=cmd.actual_minutes_per_piece,
                actual_setup_minutes=cmd.actual_setup_minutes,
                complexity=cmd.complexity,
                note=cmd.note,
                created=now,
            )
        )
        await self._uow.commit()

        replaced = f", replacing assessment #{active.id}" if active is not None else ""
        log.info(
            f"Recorded a manufacturing assessment for production order "
            f"#{production_order_id}{replaced}."
        )
        return ManufacturingAssessmentMapper.to_result(saved)
