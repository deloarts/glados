"""Converts Sequence domain entities to DTOs."""

from typing import Any

from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.mappers.controlled_document_mapper import (
    document_result_fields,
)
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.value_objects.sequence_content import steps_to_data


def _summary_fields(entity: Sequence) -> dict[str, Any]:
    return {
        **document_result_fields(entity),
        "product_id": entity.product_id,
        "product_number": entity.product_number,
        "name": entity.name,
        "step_count": len(entity.steps),
    }


class SequenceMapper:
    @staticmethod
    def to_summary_result(entity: Sequence) -> SequenceSummaryResult:
        return SequenceSummaryResult(**_summary_fields(entity))

    @staticmethod
    def to_result(entity: Sequence) -> SequenceResult:
        return SequenceResult(
            **_summary_fields(entity),
            steps=steps_to_data(entity.steps),
            frozen=entity.frozen if entity.is_released else None,
            changes=entity.changes,
        )
