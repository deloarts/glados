"""
SQLAlchemy implementations of the product device resource ports: the plain
option lists and the device kinds with their positions, parameters and
signals.
Writes only flush; the caller's unit of work commits them.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model import (
    ProductDeviceKindOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model import (
    ProductDeviceKindParameterOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model import (
    ProductDeviceKindPositionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model import (
    ProductDeviceKindSignalOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model import (
    ProductDeviceOptionOrmModel,
)
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindParameter
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindSignal
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceOptionRepository,
)


async def _write_sort_orders(
    db: AsyncSession, model: type[Any], sort_orders: dict[int, int]
) -> None:
    """Writes through the ORM, so live updates see the change. The lists are
    short and a move touches few rows."""
    for row_id, sort_order in sort_orders.items():
        orm = await db.get(model, row_id)
        if orm is not None:
            orm.sort_order = sort_order
    await db.flush()


# ── Options ───────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def product_device_option_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(ProductDeviceOptionOrmModel.creator),
        load_user(ProductDeviceOptionOrmModel.changed_by),
    )


def product_device_option_orm_to_entity(orm: ProductDeviceOptionOrmModel) -> ProductDeviceOption:
    return ProductDeviceOption(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        category=ProductDeviceOptionCategory(orm.category),
        label=LocalizedText(values=dict(orm.label or {})),
        letter=orm.letter,
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


class SqlAlchemyProductDeviceOptionRepository(IProductDeviceOptionRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> ProductDeviceOption | None:
        orm = await self._db.scalar(
            by_id(ProductDeviceOptionOrmModel, id, *product_device_option_load_options()).limit(1)
        )
        return product_device_option_orm_to_entity(orm) if orm else None

    async def get_by_letter(self, letter: str) -> ProductDeviceOption | None:
        orm = await self._db.scalar(
            select(ProductDeviceOptionOrmModel)
            .where(ProductDeviceOptionOrmModel.letter == letter)
            .options(*product_device_option_load_options())
            .limit(1)
        )
        return product_device_option_orm_to_entity(orm) if orm else None

    async def get_many(
        self, category: ProductDeviceOptionCategory | None, include_archived: bool
    ) -> list[ProductDeviceOption]:
        m = ProductDeviceOptionOrmModel
        q = select(m).options(*product_device_option_load_options())
        if category is not None:
            q = q.where(m.category == category.value)
        if not include_archived:
            q = q.where(m.archived.is_(False))
        rows = await self._db.scalars(q.order_by(m.category, m.sort_order, m.id))
        return [product_device_option_orm_to_entity(r) for r in rows]

    async def next_sort_order(self, category: ProductDeviceOptionCategory) -> int:
        m = ProductDeviceOptionOrmModel
        current = await self._db.scalar(
            select(func.max(m.sort_order)).where(m.category == category.value)
        )
        return 0 if current is None else current + 1

    async def save(self, option: ProductDeviceOption) -> ProductDeviceOption:
        values = {
            "created": option.created,
            "changed": option.changed,
            "changes": option.changes,
            "category": option.category.value,
            "label": option.label.as_dict(),
            "letter": option.letter,
            "sort_order": option.sort_order,
            "archived": option.archived,
            "creator_id": option.creator_id,
        }
        if option.id == 0:
            orm = ProductDeviceOptionOrmModel(**values)
            self._db.add(orm)
            await self._db.flush()
            row_id = orm.id
        else:
            existing = await self._db.get(ProductDeviceOptionOrmModel, option.id)
            if existing is None:
                raise ValueError(f"ProductDeviceOptionOrmModel id={option.id} not found.")
            for key, value in values.items():
                setattr(existing, key, value)
            await self._db.flush()
            row_id = option.id
        reloaded = (
            await self._db.scalars(
                by_id(
                    ProductDeviceOptionOrmModel,
                    row_id,
                    *product_device_option_load_options(),
                    refresh=True,
                )
            )
        ).one()
        return product_device_option_orm_to_entity(reloaded)

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        await _write_sort_orders(self._db, ProductDeviceOptionOrmModel, sort_orders)


# ── Kinds ─────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def product_device_kind_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(ProductDeviceKindOrmModel.creator),
        load_user(ProductDeviceKindOrmModel.changed_by),
        selectinload(ProductDeviceKindOrmModel.positions),
        selectinload(ProductDeviceKindOrmModel.parameters),
        selectinload(ProductDeviceKindOrmModel.signals),
    )


def _position_to_entity(orm: ProductDeviceKindPositionOrmModel) -> ProductDeviceKindPosition:
    return ProductDeviceKindPosition(
        id=orm.id,
        public_id=orm.public_id,
        kind_id=orm.kind_id,
        label=LocalizedText(values=dict(orm.label or {})),
        takes_value=orm.takes_value,
        unit=orm.unit,
        sort_order=orm.sort_order,
        archived=orm.archived,
        plc_state_name=orm.plc_state_name,
        plc_command_name=orm.plc_command_name,
    )


def _parameter_to_entity(orm: ProductDeviceKindParameterOrmModel) -> ProductDeviceKindParameter:
    return ProductDeviceKindParameter(
        id=orm.id,
        public_id=orm.public_id,
        kind_id=orm.kind_id,
        label=LocalizedText(values=dict(orm.label or {})),
        unit=orm.unit,
        value_type=ProductDeviceParameterType(orm.value_type),
        sort_order=orm.sort_order,
        archived=orm.archived,
    )


def _signal_to_entity(orm: ProductDeviceKindSignalOrmModel) -> ProductDeviceKindSignal:
    return ProductDeviceKindSignal(
        id=orm.id,
        public_id=orm.public_id,
        kind_id=orm.kind_id,
        label=LocalizedText(values=dict(orm.label or {})),
        signal_type=ProductDeviceSignalType(orm.signal_type),
        plc_name=orm.plc_name,
        sort_order=orm.sort_order,
        archived=orm.archived,
    )


def product_device_kind_orm_to_entity(orm: ProductDeviceKindOrmModel) -> ProductDeviceKind:
    return ProductDeviceKind(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        label=LocalizedText(values=dict(orm.label or {})),
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        without_driving_medium=orm.without_driving_medium,
        positions=[_position_to_entity(p) for p in orm.positions],
        parameters=[_parameter_to_entity(p) for p in orm.parameters],
        signals=[_signal_to_entity(s) for s in orm.signals],
    )


def _position_values(position: ProductDeviceKindPosition, kind_id: int) -> dict[str, Any]:
    return {
        "kind_id": kind_id,
        "label": position.label.as_dict(),
        "takes_value": position.takes_value,
        "unit": position.unit,
        "sort_order": position.sort_order,
        "archived": position.archived,
        "plc_state_name": position.plc_state_name,
        "plc_command_name": position.plc_command_name,
    }


def _parameter_values(parameter: ProductDeviceKindParameter, kind_id: int) -> dict[str, Any]:
    return {
        "kind_id": kind_id,
        "label": parameter.label.as_dict(),
        "unit": parameter.unit,
        "value_type": parameter.value_type.value,
        "sort_order": parameter.sort_order,
        "archived": parameter.archived,
    }


def _signal_values(signal: ProductDeviceKindSignal, kind_id: int) -> dict[str, Any]:
    return {
        "kind_id": kind_id,
        "label": signal.label.as_dict(),
        "signal_type": signal.signal_type.value,
        "plc_name": signal.plc_name,
        "sort_order": signal.sort_order,
        "archived": signal.archived,
    }


class SqlAlchemyProductDeviceKindRepository(IProductDeviceKindRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> ProductDeviceKind | None:
        orm = await self._db.scalar(
            by_id(ProductDeviceKindOrmModel, id, *product_device_kind_load_options()).limit(1)
        )
        return product_device_kind_orm_to_entity(orm) if orm else None

    async def get_many(self, include_archived: bool) -> list[ProductDeviceKind]:
        m = ProductDeviceKindOrmModel
        q = select(m).options(*product_device_kind_load_options())
        if not include_archived:
            q = q.where(m.archived.is_(False))
        rows = await self._db.scalars(q.order_by(m.sort_order, m.id))
        return [product_device_kind_orm_to_entity(r) for r in rows]

    async def next_sort_order(self) -> int:
        current = await self._db.scalar(select(func.max(ProductDeviceKindOrmModel.sort_order)))
        return 0 if current is None else current + 1

    async def save(self, kind: ProductDeviceKind) -> ProductDeviceKind:
        values = {
            "created": kind.created,
            "changed": kind.changed,
            "changes": kind.changes,
            "label": kind.label.as_dict(),
            "sort_order": kind.sort_order,
            "without_driving_medium": kind.without_driving_medium,
            "archived": kind.archived,
            "creator_id": kind.creator_id,
        }
        if kind.id == 0:
            orm = ProductDeviceKindOrmModel(**values)
            self._db.add(orm)
            await self._db.flush()
            kind_id = orm.id
        else:
            existing = await self._db.get(ProductDeviceKindOrmModel, kind.id)
            if existing is None:
                raise ValueError(f"ProductDeviceKindOrmModel id={kind.id} not found.")
            for key, value in values.items():
                setattr(existing, key, value)
            kind_id = kind.id

        await self._save_children(
            ProductDeviceKindPositionOrmModel,
            [(p.id, _position_values(p, kind_id)) for p in kind.positions],
        )
        await self._save_children(
            ProductDeviceKindParameterOrmModel,
            [(p.id, _parameter_values(p, kind_id)) for p in kind.parameters],
        )
        await self._save_children(
            ProductDeviceKindSignalOrmModel,
            [(s.id, _signal_values(s, kind_id)) for s in kind.signals],
        )
        await self._db.flush()

        reloaded = (
            await self._db.scalars(
                by_id(
                    ProductDeviceKindOrmModel,
                    kind_id,
                    *product_device_kind_load_options(),
                    refresh=True,
                )
            )
        ).one()
        return product_device_kind_orm_to_entity(reloaded)

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        await _write_sort_orders(self._db, ProductDeviceKindOrmModel, sort_orders)

    async def _save_children(
        self, model: type[Any], children: list[tuple[int, dict[str, Any]]]
    ) -> None:
        for child_id, values in children:
            if child_id == 0:
                self._db.add(model(**values))
                continue
            existing = await self._db.get(model, child_id)
            if existing is None:
                raise ValueError(f"{model.__name__} id={child_id} not found.")
            for key, value in values.items():
                setattr(existing, key, value)
