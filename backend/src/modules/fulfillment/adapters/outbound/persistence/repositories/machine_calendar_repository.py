"""
Concrete SQLAlchemy implementation of IMachineCalendarRepository.
"""

from datetime import date
from functools import lru_cache
from typing import Any
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.fulfillment.adapters.outbound.persistence.models.machine_working_hours_model import (
    MachineCalendarExceptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_working_hours_model import (
    MachineWorkingHoursOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._calendar_hours import (
    weekly_from_json,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._calendar_hours import (
    weekly_to_json,
)
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.entities.machine_working_hours import MachineWorkingHours
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.tenant_holiday_model import (
    TenantHolidayOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory

_RowT = TypeVar(
    "_RowT",
    MachineWorkingHoursOrmModel,
    MachineCalendarExceptionOrmModel,
    TenantHolidayOrmModel,
)


@lru_cache(maxsize=1)
def _working_hours_load_options() -> tuple[ORMOption, ...]:
    """Everything _working_hours_orm_to_entity() dereferences. Built on first
    call rather than at import, because constructing a loader option
    configures the mapper registry before every model module is registered."""
    return (load_user(MachineWorkingHoursOrmModel.changed_by),)


@lru_cache(maxsize=1)
def _exception_load_options() -> tuple[ORMOption, ...]:
    """Everything _exception_orm_to_entity() dereferences."""
    return (load_user(MachineCalendarExceptionOrmModel.changed_by),)


@lru_cache(maxsize=1)
def _holiday_load_options() -> tuple[ORMOption, ...]:
    """Everything _holiday_orm_to_entity() dereferences."""
    return (load_user(TenantHolidayOrmModel.changed_by),)


def _working_hours_orm_to_entity(orm: MachineWorkingHoursOrmModel) -> MachineWorkingHours:
    return MachineWorkingHours(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        weekly_hours=weekly_from_json(orm.weekly_hours),
        creator_id=orm.creator_id,
        machine_id=orm.machine_id,
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def _working_hours_entity_to_dict(item: MachineWorkingHours) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "weekly_hours": weekly_to_json(item.weekly_hours),
        "creator_id": item.creator_id,
        "machine_id": item.machine_id,
    }


def _exception_orm_to_entity(orm: MachineCalendarExceptionOrmModel) -> MachineCalendarException:
    return MachineCalendarException(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        exception_date=orm.exception_date,
        available_minutes=orm.available_minutes,
        note=orm.note,
        creator_id=orm.creator_id,
        machine_id=orm.machine_id,
        start_minute=orm.start_minute,
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def _exception_entity_to_dict(item: MachineCalendarException) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "exception_date": item.exception_date,
        "available_minutes": item.available_minutes,
        "start_minute": item.start_minute,
        "note": item.note,
        "creator_id": item.creator_id,
        "machine_id": item.machine_id,
    }


def _holiday_orm_to_entity(orm: TenantHolidayOrmModel) -> TenantHoliday:
    return TenantHoliday(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        name=orm.name,
        category=HolidayCategory(orm.category),
        start_date=orm.start_date,
        end_date=orm.end_date,
        creator_id=orm.creator_id,
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def _holiday_entity_to_dict(item: TenantHoliday) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "name": item.name,
        "category": item.category.value,
        "start_date": item.start_date,
        "end_date": item.end_date,
        "creator_id": item.creator_id,
    }


class SqlAlchemyMachineCalendarRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, model: type[_RowT], id: int, options: tuple[ORMOption, ...]) -> _RowT:
        """The row again with its changer loaded, after a flush that may have
        moved `changed` and so the changer."""
        return (await self._db.scalars(by_id(model, id, *options, refresh=True))).one()

    # ── Working hours ────────────────────────────────────────────────

    async def get_working_hours_by_machine_id(self, machine_id: int) -> MachineWorkingHours | None:
        orm = await self._db.scalar(
            select(MachineWorkingHoursOrmModel)
            .where(MachineWorkingHoursOrmModel.machine_id == machine_id)
            .options(*_working_hours_load_options())
            .limit(1)
        )
        return _working_hours_orm_to_entity(orm) if orm else None

    async def get_working_hours_by_machine_ids(
        self, machine_ids: list[int]
    ) -> list[MachineWorkingHours]:
        if not machine_ids:
            return []
        rows = (
            await self._db.scalars(
                select(MachineWorkingHoursOrmModel)
                .where(MachineWorkingHoursOrmModel.machine_id.in_(machine_ids))
                .options(*_working_hours_load_options())
            )
        ).all()
        return [_working_hours_orm_to_entity(r) for r in rows]

    async def save_working_hours(self, item: MachineWorkingHours) -> MachineWorkingHours:
        if item.id == 0:
            orm = MachineWorkingHoursOrmModel(**_working_hours_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return _working_hours_orm_to_entity(
                await self._reload(
                    MachineWorkingHoursOrmModel, orm.id, _working_hours_load_options()
                )
            )
        existing = await self._db.scalar(
            select(MachineWorkingHoursOrmModel)
            .where(MachineWorkingHoursOrmModel.id == item.id)
            .limit(1)
        )
        if not existing:
            raise ValueError(f"MachineWorkingHoursOrmModel id={item.id} not found.")
        for k, v in _working_hours_entity_to_dict(item).items():
            setattr(existing, k, v)
        await self._db.flush()
        return _working_hours_orm_to_entity(
            await self._reload(MachineWorkingHoursOrmModel, item.id, _working_hours_load_options())
        )

    async def delete_working_hours(self, item: MachineWorkingHours) -> None:
        orm = await self._db.scalar(
            select(MachineWorkingHoursOrmModel)
            .where(MachineWorkingHoursOrmModel.id == item.id)
            .limit(1)
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    # ── Calendar exceptions ──────────────────────────────────────────

    async def get_exceptions_by_machine_id(self, machine_id: int) -> list[MachineCalendarException]:
        rows = (
            await self._db.scalars(
                select(MachineCalendarExceptionOrmModel)
                .where(MachineCalendarExceptionOrmModel.machine_id == machine_id)
                .options(*_exception_load_options())
                .order_by(MachineCalendarExceptionOrmModel.exception_date)
            )
        ).all()
        return [_exception_orm_to_entity(r) for r in rows]

    async def get_exceptions_by_machine_ids(
        self, machine_ids: list[int]
    ) -> list[MachineCalendarException]:
        if not machine_ids:
            return []
        rows = (
            await self._db.scalars(
                select(MachineCalendarExceptionOrmModel)
                .where(MachineCalendarExceptionOrmModel.machine_id.in_(machine_ids))
                .options(*_exception_load_options())
                .order_by(MachineCalendarExceptionOrmModel.exception_date)
            )
        ).all()
        return [_exception_orm_to_entity(r) for r in rows]

    async def get_exception_by_id(self, id: int) -> MachineCalendarException | None:
        orm = await self._db.scalar(
            by_id(MachineCalendarExceptionOrmModel, id, *_exception_load_options()).limit(1)
        )
        return _exception_orm_to_entity(orm) if orm else None

    async def get_exception_by_machine_and_date(
        self, machine_id: int, exception_date: date
    ) -> MachineCalendarException | None:
        orm = await self._db.scalar(
            select(MachineCalendarExceptionOrmModel)
            .where(
                MachineCalendarExceptionOrmModel.machine_id == machine_id,
                MachineCalendarExceptionOrmModel.exception_date == exception_date,
            )
            .options(*_exception_load_options())
            .limit(1)
        )
        return _exception_orm_to_entity(orm) if orm else None

    async def save_exception(self, item: MachineCalendarException) -> MachineCalendarException:
        if item.id == 0:
            orm = MachineCalendarExceptionOrmModel(**_exception_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return _exception_orm_to_entity(
                await self._reload(
                    MachineCalendarExceptionOrmModel, orm.id, _exception_load_options()
                )
            )
        existing = await self._db.scalar(
            select(MachineCalendarExceptionOrmModel)
            .where(MachineCalendarExceptionOrmModel.id == item.id)
            .limit(1)
        )
        if not existing:
            raise ValueError(f"MachineCalendarExceptionOrmModel id={item.id} not found.")
        for k, v in _exception_entity_to_dict(item).items():
            setattr(existing, k, v)
        await self._db.flush()
        return _exception_orm_to_entity(
            await self._reload(MachineCalendarExceptionOrmModel, item.id, _exception_load_options())
        )

    async def delete_exception(self, item: MachineCalendarException) -> None:
        orm = await self._db.scalar(
            select(MachineCalendarExceptionOrmModel)
            .where(MachineCalendarExceptionOrmModel.id == item.id)
            .limit(1)
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    # ── Tenant holidays ──────────────────────────────────────────────

    async def get_holidays(self) -> list[TenantHoliday]:
        rows = (
            await self._db.scalars(
                select(TenantHolidayOrmModel)
                .options(*_holiday_load_options())
                .order_by(TenantHolidayOrmModel.start_date, TenantHolidayOrmModel.id)
            )
        ).all()
        return [_holiday_orm_to_entity(r) for r in rows]

    async def get_holiday_by_id(self, id: int) -> TenantHoliday | None:
        orm = await self._db.scalar(
            by_id(TenantHolidayOrmModel, id, *_holiday_load_options()).limit(1)
        )
        return _holiday_orm_to_entity(orm) if orm else None

    async def save_holiday(self, item: TenantHoliday) -> TenantHoliday:
        if item.id == 0:
            orm = TenantHolidayOrmModel(**_holiday_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return _holiday_orm_to_entity(
                await self._reload(TenantHolidayOrmModel, orm.id, _holiday_load_options())
            )
        existing = await self._db.scalar(by_id(TenantHolidayOrmModel, item.id).limit(1))
        if not existing:
            raise ValueError(f"TenantHolidayOrmModel id={item.id} not found.")
        for k, v in _holiday_entity_to_dict(item).items():
            setattr(existing, k, v)
        await self._db.flush()
        return _holiday_orm_to_entity(
            await self._reload(TenantHolidayOrmModel, item.id, _holiday_load_options())
        )

    async def delete_holiday(self, item: TenantHoliday) -> None:
        orm = await self._db.scalar(by_id(TenantHolidayOrmModel, item.id).limit(1))
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
