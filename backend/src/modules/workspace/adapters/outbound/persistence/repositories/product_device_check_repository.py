"""
Concrete SQLAlchemy implementation of IProductDeviceCheckRepository.
"""

from sqlalchemy import Select
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.workspace.adapters.outbound.persistence.models.product_device_check_model import (
    ProductDeviceCheckOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceOrmModel,
)
from src.modules.workspace.domain.entities.product_device_check import ProductDeviceCheck
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.modules.workspace.ports.outbound.repositories.product_device_check_repository import (
    IProductDeviceCheckRepository,
)


def _to_entity(orm: ProductDeviceCheckOrmModel) -> ProductDeviceCheck:
    return ProductDeviceCheck(
        id=orm.id,
        public_id=orm.public_id,
        device_id=orm.device_id,
        plan=DevicePlan(orm.plan),
        checked_by_id=orm.checked_by_id,
        checked_at=utc_aware(orm.checked_at),
        checked_by_name=orm.checked_by.full_name if orm.checked_by else "",
    )


class SqlAlchemyProductDeviceCheckRepository(IProductDeviceCheckRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _query(self) -> Select[tuple[ProductDeviceCheckOrmModel]]:
        return select(ProductDeviceCheckOrmModel).options(
            selectinload(ProductDeviceCheckOrmModel.checked_by)
        )

    async def get_by_product(self, product_id: int) -> list[ProductDeviceCheck]:
        devices = select(ProductDeviceOrmModel.id).where(
            ProductDeviceOrmModel.product_id == product_id
        )
        rows = await self._db.scalars(
            self._query().where(ProductDeviceCheckOrmModel.device_id.in_(devices))
        )
        return [_to_entity(r) for r in rows]

    async def get(self, device_id: int, plan: DevicePlan) -> ProductDeviceCheck | None:
        m = ProductDeviceCheckOrmModel
        orm = await self._db.scalar(
            self._query().where(m.device_id == device_id, m.plan == plan.value).limit(1)
        )
        return _to_entity(orm) if orm else None

    async def add(self, check: ProductDeviceCheck) -> ProductDeviceCheck:
        orm = ProductDeviceCheckOrmModel(
            device_id=check.device_id,
            plan=check.plan.value,
            checked_by_id=check.checked_by_id,
            checked_at=check.checked_at,
        )
        self._db.add(orm)
        await self._db.flush()
        found = await self.get(check.device_id, check.plan)
        assert found is not None
        return found

    async def remove(self, device_id: int, plan: DevicePlan) -> None:
        m = ProductDeviceCheckOrmModel
        await self._db.execute(delete(m).where(m.device_id == device_id, m.plan == plan.value))
        await self._db.flush()

    async def remove_all(self, device_id: int) -> int:
        m = ProductDeviceCheckOrmModel
        result = await self._db.execute(delete(m).where(m.device_id == device_id))
        await self._db.flush()
        return int(getattr(result, "rowcount", 0) or 0)
