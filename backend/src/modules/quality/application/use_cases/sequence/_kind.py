"""
Binds flow sequences to the shared controlled document use cases in
use_cases/_controlled_documents/. A new sequence revision stays a draft
beside the released one, which remains the valid record until the new
revision is released.
"""

from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.mappers.sequence_mapper import SequenceMapper
from src.modules.quality.application.use_cases._controlled_documents.kind import (
    ControlledDocumentKind,
)
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.services.sequence_rules import ACCESS
from src.modules.quality.domain.services.sequence_rules import SequenceRules

KIND: ControlledDocumentKind[Sequence, SequenceResult, SequenceSummaryResult] = (
    ControlledDocumentKind(
        access=ACCESS,
        rules=SequenceRules,
        live_resource=LiveResource.SEQUENCES,
        to_result=SequenceMapper.to_result,
        to_summary_result=SequenceMapper.to_summary_result,
        title=lambda sequence: sequence.name,
        takes_over_now=lambda _sequence: False,
    )
)
