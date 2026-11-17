"""
Concrete SQLAlchemy implementation of IMachineDowntimeRepository.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.fulfillment.adapters.outbound.persistence.models.machine_downtime_model import (
    MachineDowntimeOrmModel,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    MachineDowntimeFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.shared_kernel.domain.services.clock import now_utc


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences. Built on first call rather
    than at import, because constructing a loader option configures the mapper
    registry before every model module is registered."""
    return (
        selectinload(MachineDowntimeOrmModel.machine),
        load_user(MachineDowntimeOrmModel.reported_by),
        load_user(MachineDowntimeOrmModel.ended_by),
        load_user(MachineDowntimeOrmModel.changed_by),
    )


def _orm_to_entity(orm: MachineDowntimeOrmModel) -> MachineDowntime:
    started_at = utc_aware(orm.started_at)
    created = utc_aware(orm.created)
    assert started_at is not None  # non-null column
    assert created is not None  # non-null column
    return MachineDowntime(
        id=orm.id,
        public_id=orm.public_id,
        created=created,
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        machine_id=orm.machine_id,
        started_at=started_at,
        ended_at=utc_aware(orm.ended_at),
        reason=MachineDowntimeReason(orm.reason),
        note=orm.note,
        reported_by_id=orm.reported_by_id,
        ended_by_id=orm.ended_by_id,
        machine_internal_name=orm.machine.internal_name if orm.machine else "",
        reported_by_full_name=orm.reported_by.full_name if orm.reported_by else "",
        ended_by_full_name=orm.ended_by.full_name if orm.ended_by else None,
        changed_by_id=orm.changed_by_id,
        changed_by_full_name=orm.changed_by.full_name if orm.changed_by else None,
    )


def _entity_to_dict(item: MachineDowntime) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "machine_id": item.machine_id,
        "started_at": item.started_at,
        "ended_at": item.ended_at,
        "reason": item.reason.value,
        "note": item.note,
        "reported_by_id": item.reported_by_id,
        "ended_by_id": item.ended_by_id,
    }


class SqlAlchemyMachineDowntimeRepository:
    """Implements IMachineDowntimeRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> MachineDowntime | None:
        orm = await self._db.scalar(by_id(MachineDowntimeOrmModel, id, *_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_for_update(self, id: int) -> MachineDowntime | None:
        orm = await self._db.scalar(
            by_id(
                MachineDowntimeOrmModel, id, *_load_options(), for_update=True, refresh=True
            ).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_multi(
        self, filters: MachineDowntimeFilterDto
    ) -> tuple[int, list[MachineDowntime]]:
        q = select(MachineDowntimeOrmModel)
        if filters.machine_id is not None:
            q = q.where(MachineDowntimeOrmModel.machine_id == filters.machine_id)
        if filters.reason is not None:
            q = q.where(MachineDowntimeOrmModel.reason == filters.reason)
        if filters.open_only:
            q = q.where(MachineDowntimeOrmModel.ended_at.is_(None))
        # Period filter is window-overlap, not a strict started_at range: a
        # downtime that started before the period but is still open (or
        # ended inside it) still belongs to the period being reviewed.
        if filters.started_to is not None:
            q = q.where(MachineDowntimeOrmModel.started_at <= filters.started_to)
        if filters.started_from is not None:
            q = q.where(
                (MachineDowntimeOrmModel.ended_at.is_(None))
                | (MachineDowntimeOrmModel.ended_at >= filters.started_from)
            )

        sort_col = (
            MachineDowntimeOrmModel.machine_id
            if filters.order_by == "machine_id"
            else MachineDowntimeOrmModel.started_at
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            desc(MachineDowntimeOrmModel.id),
            options=_load_options(),
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def get_open_by_machine_ids(
        self, machine_ids: list[int], *, started_by: datetime | None = None
    ) -> dict[int, MachineDowntime]:
        if not machine_ids:
            return {}
        query = select(MachineDowntimeOrmModel).where(
            MachineDowntimeOrmModel.machine_id.in_(machine_ids),
            MachineDowntimeOrmModel.ended_at.is_(None),
        )
        if started_by is not None:
            query = query.where(MachineDowntimeOrmModel.started_at <= started_by)
        rows = (await self._db.scalars(query.options(*_load_options()))).all()
        return {r.machine_id: _orm_to_entity(r) for r in rows}

    async def get_overlapping(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> list[MachineDowntime]:
        if not machine_ids:
            return []
        rows = (
            await self._db.scalars(
                select(MachineDowntimeOrmModel)
                .where(
                    MachineDowntimeOrmModel.machine_id.in_(machine_ids),
                    MachineDowntimeOrmModel.started_at < end,
                    (MachineDowntimeOrmModel.ended_at.is_(None))
                    | (MachineDowntimeOrmModel.ended_at > start),
                )
                .options(*_load_options())
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def minutes_by_machine_in_period(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> dict[int, int]:
        """Summed in Python, not SQL: datetime subtraction is not portable
        between SQLite and Postgres, and the row count per machine/period
        is always small."""
        if not machine_ids:
            return {}
        rows = (
            await self._db.scalars(
                select(MachineDowntimeOrmModel).where(
                    MachineDowntimeOrmModel.machine_id.in_(machine_ids),
                    MachineDowntimeOrmModel.started_at < end,
                    (MachineDowntimeOrmModel.ended_at.is_(None))
                    | (MachineDowntimeOrmModel.ended_at > start),
                )
            )
        ).all()
        now = now_utc()
        totals: dict[int, int] = {}
        for row in rows:
            window_end = min(utc_aware(row.ended_at) or now, end)
            window_start = max(utc_aware(row.started_at) or now, start)
            minutes = max(0, int((window_end - window_start).total_seconds() // 60))
            totals[row.machine_id] = totals.get(row.machine_id, 0) + minutes
        return totals

    async def save(self, item: MachineDowntime) -> MachineDowntime:
        if item.id == 0:
            orm = MachineDowntimeOrmModel(**_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return _orm_to_entity(await self._reload(orm.id))
        existing = await self._db.scalar(
            select(MachineDowntimeOrmModel).where(MachineDowntimeOrmModel.id == item.id).limit(1)
        )
        if not existing:
            raise ValueError(f"MachineDowntimeOrmModel id={item.id} not found.")
        for k, v in _entity_to_dict(item).items():
            setattr(existing, k, v)
        await self._db.flush()
        return _orm_to_entity(await self._reload(item.id))

    async def _reload(self, id: int) -> MachineDowntimeOrmModel:
        return (
            await self._db.scalars(
                by_id(MachineDowntimeOrmModel, id, *_load_options(), refresh=True)
            )
        ).one()

    async def delete(self, item: MachineDowntime) -> None:
        orm = await self._db.scalar(
            select(MachineDowntimeOrmModel).where(MachineDowntimeOrmModel.id == item.id).limit(1)
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
