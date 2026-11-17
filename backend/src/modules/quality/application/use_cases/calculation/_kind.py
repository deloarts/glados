"""
Binds the calculation types to the shared controlled document use cases in
use_cases/_controlled_documents/. A new calculation revision stays a draft
beside the released one, which remains the valid record until the new
revision is released.
"""

from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.mappers.calculation_mapper import CalculationMapper
from src.modules.quality.application.use_cases._controlled_documents.kind import (
    ControlledDocumentKind,
)
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.services.calculation_rules import ACCESS
from src.modules.quality.domain.services.calculation_rules import CalculationRules

KIND: ControlledDocumentKind[Calculation, CalculationResult, CalculationSummaryResult] = (
    ControlledDocumentKind(
        access=ACCESS,
        rules=CalculationRules,
        live_resource=LiveResource.CALCULATIONS,
        to_result=CalculationMapper.to_result,
        to_summary_result=CalculationMapper.to_summary_result,
        title=lambda calculation: calculation.title,
        takes_over_now=lambda _calculation: False,
    )
)
