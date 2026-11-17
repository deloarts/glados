"""
SQLAlchemy implementation of IProductDeviceRepository. A device is saved
together with its components; components that are no longer listed are
deleted, since they are parts of the device and nothing else references
them. Writes only flush; the caller's unit of work commits them.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.edit_version_tracking import (
    bump_edit_version_by_hand,
)
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceComponentOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceOrmModel,
)
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)


@lru_cache(maxsize=1)
def product_device_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(ProductDeviceOrmModel.creator),
        load_user(ProductDeviceOrmModel.changed_by),
        selectinload(ProductDeviceOrmModel.product),
        selectinload(ProductDeviceOrmModel.driving_medium),
        selectinload(ProductDeviceOrmModel.components).selectinload(
            ProductDeviceComponentOrmModel.bought_item
        ),
    )


def _component_to_entity(orm: ProductDeviceComponentOrmModel) -> ProductDeviceComponent:
    return ProductDeviceComponent(
        id=orm.id,
        public_id=orm.public_id,
        device_id=orm.device_id,
        product_id=orm.product_id,
        role_id=orm.role_id,
        sort_order=orm.sort_order,
        bought_item_id=orm.bought_item_id,
        eplan_tag=orm.eplan_tag,
        b10d_cycles=orm.b10d_cycles,
        mttfd_years=orm.mttfd_years,
        note=orm.note,
        signals=[
            ProductDeviceSignal(
                ProductDeviceSignalType(s["signal_type"]),
                s["meaning"],
                s["confirms_position_id"],
                s["drives_position_id"],
                bool(s["safety"]),
                s["address"],
                s["tag_suffix"],
                s["tag_name"],
                s["kind_signal_id"],
            )
            for s in orm.signals or []
        ],
        bought_item_part_number=orm.bought_item.part_number if orm.bought_item else None,
        bought_item_article_name=orm.bought_item.article_name if orm.bought_item else None,
    )


def product_device_orm_to_entity(orm: ProductDeviceOrmModel) -> ProductDevice:
    return ProductDevice(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        product_id=orm.product_id,
        location=orm.location,
        name=orm.name,
        driving_medium_id=orm.driving_medium_id,
        number=orm.number,
        name_utf8=orm.name_utf8,
        name_ascii=orm.name_ascii,
        name_ascii_key=orm.name_ascii_key,
        group_key=orm.group_key,
        kind_id=orm.kind_id,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        description=orm.description,
        initial_position_id=orm.initial_position_id,
        initial_position_value=orm.initial_position_value,
        energy_loss_behaviour_id=orm.energy_loss_behaviour_id,
        energy_restoration_behaviour_id=orm.energy_restoration_behaviour_id,
        monitoring_time_ms=orm.monitoring_time_ms,
        driven_by_id=orm.driven_by_id,
        driven_position_map=dict(orm.driven_position_map or {}),
        safety_relevant=orm.safety_relevant,
        parameters=dict(orm.parameters or {}),
        position_labels=dict(orm.position_labels or {}),
        travel_times_ms=dict(orm.travel_times_ms or {}),
        rendering_file_id=orm.rendering_file_id,
        assembly_file_id=orm.assembly_file_id,
        marker_x=orm.marker_x,
        marker_y=orm.marker_y,
        components=[_component_to_entity(c) for c in orm.components],
        product_number=orm.product.product_number,
        driving_medium_letter=orm.driving_medium.letter if orm.driving_medium else None,
        edit_version=orm.edit_version,
    )


def _components_differ(
    device: ProductDevice, stored: dict[int, ProductDeviceComponentOrmModel]
) -> bool:
    """Whether the save adds, removes or changes a component of the device."""
    if {c.id for c in device.components} != set(stored):
        return True
    return any(
        getattr(stored[c.id], key) != value
        for c in device.components
        for key, value in _component_values(c, device.id, device.product_id).items()
    )


def _device_values(device: ProductDevice) -> dict[str, Any]:
    return {
        "created": device.created,
        "changed": device.changed,
        "changes": device.changes,
        "archived": device.archived,
        "product_id": device.product_id,
        "location": device.location,
        "name": device.name,
        "driving_medium_id": device.driving_medium_id,
        "number": device.number,
        "name_utf8": device.name_utf8,
        "name_ascii": device.name_ascii,
        "name_ascii_key": device.name_ascii_key,
        "group_key": device.group_key,
        "kind_id": device.kind_id,
        "description": device.description,
        "initial_position_id": device.initial_position_id,
        "initial_position_value": device.initial_position_value,
        "energy_loss_behaviour_id": device.energy_loss_behaviour_id,
        "energy_restoration_behaviour_id": device.energy_restoration_behaviour_id,
        "monitoring_time_ms": device.monitoring_time_ms,
        "driven_by_id": device.driven_by_id,
        "driven_position_map": device.driven_position_map,
        "safety_relevant": device.safety_relevant,
        "parameters": dict(device.parameters),
        "position_labels": dict(device.position_labels),
        "travel_times_ms": dict(device.travel_times_ms),
        "rendering_file_id": device.rendering_file_id,
        "assembly_file_id": device.assembly_file_id,
        "marker_x": device.marker_x,
        "marker_y": device.marker_y,
        "creator_id": device.creator_id,
    }


def _component_values(
    component: ProductDeviceComponent, device_id: int, product_id: int
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "product_id": product_id,
        "role_id": component.role_id,
        "sort_order": component.sort_order,
        "bought_item_id": component.bought_item_id,
        "eplan_tag": component.eplan_tag,
        "b10d_cycles": component.b10d_cycles,
        "mttfd_years": component.mttfd_years,
        "note": component.note,
        "signals": [
            {
                "signal_type": s.signal_type.value,
                "meaning": s.meaning,
                "confirms_position_id": s.confirms_position_id,
                "drives_position_id": s.drives_position_id,
                "safety": s.safety,
                "address": s.address,
                "tag_suffix": s.tag_suffix,
                "tag_name": s.tag_name,
                "kind_signal_id": s.kind_signal_id,
            }
            for s in component.signals
        ],
    }


class SqlAlchemyProductDeviceRepository(IProductDeviceRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> ProductDevice | None:
        orm = await self._db.scalar(
            by_id(ProductDeviceOrmModel, id, *product_device_load_options()).limit(1)
        )
        return product_device_orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, ProductDeviceOrmModel, id)

    async def get_by_product(self, product_id: int, include_archived: bool) -> list[ProductDevice]:
        m = ProductDeviceOrmModel
        q = select(m).where(m.product_id == product_id).options(*product_device_load_options())
        if not include_archived:
            q = q.where(m.archived.is_(False))
        rows = await self._db.scalars(q.order_by(m.name_utf8, m.id))
        return [product_device_orm_to_entity(r) for r in rows]

    async def _one_where(self, *criteria: Any) -> ProductDevice | None:
        orm = await self._db.scalar(
            select(ProductDeviceOrmModel)
            .where(*criteria)
            .options(*product_device_load_options())
            .limit(1)
        )
        return product_device_orm_to_entity(orm) if orm else None

    async def get_by_name(self, product_id: int, name_utf8: str) -> ProductDevice | None:
        m = ProductDeviceOrmModel
        return await self._one_where(m.product_id == product_id, m.name_utf8 == name_utf8)

    async def get_by_ascii_key(self, product_id: int, name_ascii_key: str) -> ProductDevice | None:
        m = ProductDeviceOrmModel
        return await self._one_where(m.product_id == product_id, m.name_ascii_key == name_ascii_key)

    async def max_number(self, product_id: int, group_key: str) -> int | None:
        m = ProductDeviceOrmModel
        highest: int | None = await self._db.scalar(
            select(func.max(m.number)).where(m.product_id == product_id, m.group_key == group_key)
        )
        return highest

    async def count_by_product(self, product_id: int) -> int:
        m = ProductDeviceOrmModel
        count = await self._db.scalar(select(func.count(m.id)).where(m.product_id == product_id))
        return count or 0

    async def count_by_driving_medium(self, option_id: int) -> int:
        m = ProductDeviceOrmModel
        count = await self._db.scalar(
            select(func.count(m.id)).where(m.driving_medium_id == option_id)
        )
        return count or 0

    async def count_driven_by(self, device_id: int) -> int:
        m = ProductDeviceOrmModel
        count = await self._db.scalar(select(func.count(m.id)).where(m.driven_by_id == device_id))
        return count or 0

    async def get_component_by_eplan_tag(
        self, product_id: int, eplan_tag: str
    ) -> ProductDeviceComponent | None:
        c = ProductDeviceComponentOrmModel
        orm = await self._db.scalar(
            select(c)
            .where(c.product_id == product_id, c.eplan_tag == eplan_tag)
            .options(selectinload(c.bought_item))
            .limit(1)
        )
        return _component_to_entity(orm) if orm else None

    async def save(self, device: ProductDevice) -> ProductDevice:
        values = _device_values(device)
        if device.id == 0:
            orm = ProductDeviceOrmModel(**values)
            self._db.add(orm)
            await self._db.flush()
            device_id = orm.id
            stored: dict[int, ProductDeviceComponentOrmModel] = {}
        else:
            existing = await self._db.get(ProductDeviceOrmModel, device.id)
            if existing is None:
                raise ValueError(f"ProductDeviceOrmModel id={device.id} not found.")
            for key, value in values.items():
                setattr(existing, key, value)
            device_id = device.id
            rows = await self._db.scalars(
                select(ProductDeviceComponentOrmModel).where(
                    ProductDeviceComponentOrmModel.device_id == device_id
                )
            )
            stored = {row.id: row for row in rows}
            if _components_differ(device, stored):
                # The components are the device's own fields on the edit
                # form, kept in a table of their own.
                bump_edit_version_by_hand(existing)

        # Deletes and cleared tags first, so a tag that moves between
        # components in one save never meets itself in the unique index.
        kept = {c.id for c in device.components if c.id}
        for row_id, row in stored.items():
            if row_id not in kept:
                await self._db.delete(row)
            else:
                row.eplan_tag = None
        await self._db.flush()

        for component in device.components:
            component_values = _component_values(component, device_id, device.product_id)
            if component.id == 0:
                self._db.add(ProductDeviceComponentOrmModel(**component_values))
                continue
            stored_row = stored.get(component.id)
            if stored_row is None:
                raise ValueError(f"Component id={component.id} is not part of device {device_id}.")
            for key, value in component_values.items():
                setattr(stored_row, key, value)
        await self._db.flush()

        reloaded = (
            await self._db.scalars(
                by_id(
                    ProductDeviceOrmModel, device_id, *product_device_load_options(), refresh=True
                )
            )
        ).one()
        return product_device_orm_to_entity(reloaded)
