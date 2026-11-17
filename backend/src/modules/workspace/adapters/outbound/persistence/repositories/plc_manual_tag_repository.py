"""
Concrete SQLAlchemy implementation of IPlcManualTagRepository.
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.workspace.adapters.outbound.persistence.models.plc_manual_tag_model import (
    PlcManualTagOrmModel,
)
from src.modules.workspace.domain.entities.plc_manual_tag import PlcManualTag
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.modules.workspace.ports.outbound.repositories.plc_manual_tag_repository import (
    IPlcManualTagRepository,
)


def _to_entity(orm: PlcManualTagOrmModel) -> PlcManualTag:
    return PlcManualTag(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        product_id=orm.product_id,
        name=orm.name,
        signal_type=ProductDeviceSignalType(orm.signal_type),
        safety=orm.safety,
        address=orm.address,
        comment=orm.comment,
        sort_order=orm.sort_order,
        creator_id=orm.creator_id,
        changed_by_id=orm.changed_by_id,
    )


def _values(tag: PlcManualTag) -> dict[str, Any]:
    return {
        "created": tag.created,
        "changed": tag.changed,
        "product_id": tag.product_id,
        "name": tag.name,
        "signal_type": tag.signal_type.value,
        "safety": tag.safety,
        "address": tag.address,
        "comment": tag.comment,
        "sort_order": tag.sort_order,
        "creator_id": tag.creator_id,
    }


class SqlAlchemyPlcManualTagRepository(IPlcManualTagRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> PlcManualTag | None:
        orm = await self._db.get(PlcManualTagOrmModel, id, populate_existing=True)
        return _to_entity(orm) if orm else None

    async def get_by_product(self, product_id: int) -> list[PlcManualTag]:
        m = PlcManualTagOrmModel
        rows = await self._db.scalars(
            select(m).where(m.product_id == product_id).order_by(m.sort_order, m.id)
        )
        return [_to_entity(r) for r in rows]

    async def next_sort_order(self, product_id: int) -> int:
        m = PlcManualTagOrmModel
        current = await self._db.scalar(
            select(func.max(m.sort_order)).where(m.product_id == product_id)
        )
        return 0 if current is None else current + 1

    async def save(self, tag: PlcManualTag) -> PlcManualTag:
        values = _values(tag)
        if tag.id == 0:
            orm = PlcManualTagOrmModel(**values)
            self._db.add(orm)
        else:
            found = await self._db.get(PlcManualTagOrmModel, tag.id)
            if found is None:
                raise ValueError(f"PlcManualTagOrmModel id={tag.id} not found.")
            orm = found
            for key, value in values.items():
                setattr(orm, key, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return _to_entity(orm)

    async def delete(self, tag: PlcManualTag) -> None:
        orm = await self._db.get(PlcManualTagOrmModel, tag.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()
