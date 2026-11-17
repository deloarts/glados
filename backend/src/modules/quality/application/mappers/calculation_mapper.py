"""Converts Calculation domain entities to DTOs."""

from typing import Any

from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.mappers.controlled_document_mapper import (
    document_result_fields,
)
from src.modules.quality.domain.entities.calculation import Calculation


def _summary_fields(entity: Calculation) -> dict[str, Any]:
    return {
        **document_result_fields(entity),
        "tool": entity.tool,
        "title": entity.title,
        "note": entity.note,
        "results": entity.results,
        "input_version": entity.input_version,
        "engine_version": entity.engine_version,
        "project_id": entity.project_id,
        "project_number": entity.project_number,
        "product_id": entity.product_id,
        "product_number": entity.product_number,
        "product_device_id": entity.product_device_id,
        "product_device_name": entity.device_name,
    }


class CalculationMapper:
    @staticmethod
    def to_summary_result(entity: Calculation) -> CalculationSummaryResult:
        return CalculationSummaryResult(**_summary_fields(entity))

    @staticmethod
    def to_result(entity: Calculation) -> CalculationResult:
        return CalculationResult(
            **_summary_fields(entity), inputs=entity.inputs, changes=entity.changes
        )
