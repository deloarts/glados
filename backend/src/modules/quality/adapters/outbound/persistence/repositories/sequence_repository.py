"""
Concrete SQLAlchemy implementation of ISequenceRepository. The queries
every controlled document runs the same way come from
controlled_document_repository.py and the document control fields are
mapped by controlled_document_mapping.py; this module adds the sequence
columns. A sequence has no project and is searched and sorted by its name.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.quality.adapters.outbound.persistence.models.sequence_model import SequenceOrmModel
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_mapping import (
    document_fields,
)
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_mapping import (
    document_values,
)
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_repository import (
    ControlledDocumentRepositoryBase,
)
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.value_objects.sequence_content import steps_from_data
from src.modules.quality.domain.value_objects.sequence_content import steps_to_data
from src.modules.quality.ports.outbound.repositories.sequence_repository import SequenceFilterDto


class SqlAlchemySequenceRepository(ControlledDocumentRepositoryBase[Sequence, SequenceFilterDto]):
    """Implements ISequenceRepository."""

    _model = SequenceOrmModel
    _number_family = NumberFamily.SEQUENCE
    _title_column = "name"
    _has_project = False

    def _orm_to_entity(self, orm: SequenceOrmModel) -> Sequence:
        return Sequence(
            **document_fields(orm),
            product_id=orm.product_id,
            product_number=orm.product.product_number if orm.product else None,
            name=orm.name,
            steps=steps_from_data(list(orm.steps or [])),
            frozen=dict(orm.frozen) if orm.frozen is not None else None,
        )

    def _entity_to_dict(self, item: Sequence) -> dict[str, Any]:
        return {
            **document_values(item),
            "product_id": item.product_id,
            "name": item.name,
            "steps": steps_to_data(item.steps),
            "frozen": item.frozen,
        }
