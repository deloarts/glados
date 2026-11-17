"""
Concrete SQLAlchemy implementation of IChecklistRepository. The queries
every controlled document runs the same way come from
controlled_document_repository.py and the document control fields are
mapped by controlled_document_mapping.py; this module adds the checklist
columns and the type and verdict filters and sorts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.quality.adapters.outbound.persistence.models.checklist_model import (
    ChecklistOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_mapping import (
    document_fields,
)
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_mapping import (
    document_values,
)
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_repository import (
    ControlledDocumentRepositoryBase,
)
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict
from src.modules.quality.ports.outbound.repositories.checklist_repository import ChecklistFilterDto


def _strings(value: dict[str, Any] | None) -> dict[str, str]:
    return {str(k): str(v) for k, v in (value or {}).items()}


class SqlAlchemyChecklistRepository(
    ControlledDocumentRepositoryBase[Checklist, ChecklistFilterDto]
):
    """Implements IChecklistRepository."""

    _model = ChecklistOrmModel
    _number_family = NumberFamily.CHECKLIST

    def _orm_to_entity(self, orm: ChecklistOrmModel) -> Checklist:
        return Checklist(
            **document_fields(orm),
            type=orm.type,
            title=orm.title,
            header=_strings(orm.header),
            answers=_strings(orm.answers),
            remarks=_strings(orm.remarks),
            definition_version=orm.definition_version,
            item_count=orm.item_count,
            answered_count=orm.answered_count,
            finding_count=orm.finding_count,
            verdict=ChecklistVerdict(orm.verdict),
            project_id=orm.project_id,
            product_id=orm.product_id,
            project_number=orm.project.project_number if orm.project else None,
            product_number=orm.product.product_number if orm.product else None,
        )

    def _entity_to_dict(self, item: Checklist) -> dict[str, Any]:
        return {
            **document_values(item),
            "type": item.type,
            "title": item.title,
            "header": item.header,
            "answers": item.answers,
            "remarks": item.remarks,
            "definition_version": item.definition_version,
            "item_count": item.item_count,
            "answered_count": item.answered_count,
            "finding_count": item.finding_count,
            "verdict": item.verdict.value,
            "project_id": item.project_id,
            "product_id": item.product_id,
        }

    def _kind_filters(self, filters: ChecklistFilterDto) -> list[FilterSpec]:
        return [
            when_not_none(filters.type, lambda type_: ChecklistOrmModel.type == type_),
            when_not_none(filters.verdict, lambda verdict: ChecklistOrmModel.verdict == verdict),
        ]

    def _kind_sort_columns(self) -> dict[str, Any]:
        return {"type": ChecklistOrmModel.type, "verdict": ChecklistOrmModel.verdict}
