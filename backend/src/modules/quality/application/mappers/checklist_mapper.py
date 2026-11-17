"""Converts Checklist domain entities to DTOs."""

from typing import Any

from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.mappers.controlled_document_mapper import (
    document_result_fields,
)
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.services.checklist_rules import ChecklistRules


def _summary_fields(entity: Checklist) -> dict[str, Any]:
    return {
        **document_result_fields(entity),
        "type": entity.type,
        "title": entity.title,
        "definition_version": entity.definition_version,
        "item_count": entity.item_count,
        "answered_count": entity.answered_count,
        "finding_count": entity.finding_count,
        "verdict": entity.verdict.value,
        "project_id": entity.project_id,
        "project_number": entity.project_number,
        "product_id": entity.product_id,
        "product_number": entity.product_number,
        "release_required": entity.release_required,
        "finished": ChecklistRules.is_finished(entity),
        "designation": entity.header.get("designation") or None,
    }


class ChecklistMapper:
    @staticmethod
    def to_summary_result(entity: Checklist) -> ChecklistSummaryResult:
        return ChecklistSummaryResult(**_summary_fields(entity))

    @staticmethod
    def to_result(entity: Checklist) -> ChecklistResult:
        return ChecklistResult(
            **_summary_fields(entity),
            header=entity.header,
            answers=entity.answers,
            remarks=entity.remarks,
            changes=entity.changes,
        )
