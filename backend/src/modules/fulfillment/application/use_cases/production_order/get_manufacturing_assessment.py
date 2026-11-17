"""Use case for retrieving a production order's manufacturing assessment."""

from src.modules.fulfillment.application.dto.production_order_dto import (
    ManufacturingAssessmentResult,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ManufacturingAssessmentMapper,
)
from src.modules.fulfillment.domain.errors import ManufacturingAssessmentNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.manufacturing_assessment_repository import (
    IManufacturingAssessmentRepository,
)


class GetManufacturingAssessment:
    def __init__(self, assessment_repo: IManufacturingAssessmentRepository) -> None:
        self._assessments = assessment_repo

    async def execute(self, production_order_id: int) -> ManufacturingAssessmentResult:
        assessment = await self._assessments.get_by_production_order_id(production_order_id)
        if not assessment:
            raise ManufacturingAssessmentNotFoundError(
                f"Production order #{production_order_id} has no manufacturing assessment."
            )
        return ManufacturingAssessmentMapper.to_result(assessment)
