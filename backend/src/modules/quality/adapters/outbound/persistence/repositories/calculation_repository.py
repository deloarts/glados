"""
Concrete SQLAlchemy implementation of ICalculationRepository. The queries
every controlled document runs the same way come from
controlled_document_repository.py and the document control fields are
mapped by controlled_document_mapping.py; this module adds the calculation
columns, the tool filter and sort and the personal-only filter.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.quality.adapters.outbound.persistence.models.calculation_model import (
    CalculationOrmModel,
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
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    CalculationFilterDto,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceOrmModel,
)
from src.modules.workspace.domain.policies.product_device_naming import DeviceName
from src.modules.workspace.domain.policies.product_device_naming import with_product_number


@lru_cache(maxsize=1)
def _device_load_options() -> tuple[ORMOption, ...]:
    return (
        selectinload(CalculationOrmModel.product_device).selectinload(
            ProductDeviceOrmModel.product
        ),
    )


def _device_name(orm: CalculationOrmModel) -> str | None:
    device = orm.product_device
    if device is None:
        return None
    return with_product_number(
        device.product.product_number, DeviceName(device.name_utf8, device.name_ascii)
    ).utf8


class SqlAlchemyCalculationRepository(
    ControlledDocumentRepositoryBase[Calculation, CalculationFilterDto]
):
    """Implements ICalculationRepository."""

    _model = CalculationOrmModel
    _number_family = NumberFamily.CALCULATION

    def _orm_to_entity(self, orm: CalculationOrmModel) -> Calculation:
        return Calculation(
            **document_fields(orm),
            tool=orm.tool,
            title=orm.title,
            note=orm.note,
            inputs=dict(orm.inputs or {}),
            results=dict(orm.results or {}),
            input_version=orm.input_version,
            engine_version=orm.engine_version,
            project_id=orm.project_id,
            product_id=orm.product_id,
            project_number=orm.project.project_number if orm.project else None,
            product_number=orm.product.product_number if orm.product else None,
            product_device_id=orm.product_device_id,
            product_device_name=orm.product_device_name,
            product_device_current_name=_device_name(orm),
        )

    def _entity_to_dict(self, item: Calculation) -> dict[str, Any]:
        return {
            **document_values(item),
            "tool": item.tool,
            "title": item.title,
            "note": item.note,
            "inputs": item.inputs,
            "results": item.results,
            "input_version": item.input_version,
            "engine_version": item.engine_version,
            "project_id": item.project_id,
            "product_id": item.product_id,
            "product_device_id": item.product_device_id,
            "product_device_name": item.product_device_name,
        }

    def _kind_load_options(self) -> tuple[ORMOption, ...]:
        return _device_load_options()

    def _kind_filters(self, filters: CalculationFilterDto) -> list[FilterSpec]:
        return [
            when(
                filters.personal_only,
                lambda _: and_(
                    CalculationOrmModel.project_id.is_(None),
                    CalculationOrmModel.product_id.is_(None),
                ),
            ),
            when_not_none(filters.tool, lambda tool: CalculationOrmModel.tool == tool),
            when_not_none(
                filters.product_device_id,
                lambda device_id: CalculationOrmModel.product_device_id == device_id,
            ),
        ]

    def _kind_sort_columns(self) -> dict[str, Any]:
        return {"tool": CalculationOrmModel.tool}
