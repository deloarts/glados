"""
Concrete SQLAlchemy implementation of IPlcEnvironmentRepository.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.workspace.adapters.outbound.persistence.models.plc_environment_model import (
    PlcEnvironmentOrmModel,
)
from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.value_objects.plc_environment_settings import CharConversion
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumn
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumnSource
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)


def _to_entity(orm: PlcEnvironmentOrmModel) -> PlcEnvironment:
    return PlcEnvironment(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=orm.name,
        is_default=orm.is_default,
        prefixes=dict(orm.prefixes or {}),
        max_tag_length=orm.max_tag_length,
        conversions=[CharConversion(c["source"], c["target"]) for c in orm.conversions or []],
        tag_table=orm.tag_table,
        safety_tag_table=orm.safety_tag_table,
        export_sheet=orm.export_sheet,
        export_columns=[
            ExportColumn(c["header"], ExportColumnSource(c["source"]), c["value"])
            for c in orm.export_columns or []
        ],
        creator_id=orm.creator_id,
        changed_by_id=orm.changed_by_id,
    )


def _values(environment: PlcEnvironment) -> dict[str, Any]:
    return {
        "created": environment.created,
        "changed": environment.changed,
        "changes": environment.changes,
        "name": environment.name,
        "name_key": environment.name.lower(),
        "is_default": environment.is_default,
        "prefixes": environment.prefixes,
        "max_tag_length": environment.max_tag_length,
        "conversions": [{"source": c.source, "target": c.target} for c in environment.conversions],
        "tag_table": environment.tag_table,
        "safety_tag_table": environment.safety_tag_table,
        "export_sheet": environment.export_sheet,
        "export_columns": [
            {"header": c.header, "source": c.source.value, "value": c.value}
            for c in environment.export_columns
        ],
        "archived": environment.archived,
        "creator_id": environment.creator_id,
    }


class SqlAlchemyPlcEnvironmentRepository(IPlcEnvironmentRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> PlcEnvironment | None:
        orm = await self._db.get(PlcEnvironmentOrmModel, id, populate_existing=True)
        return _to_entity(orm) if orm else None

    async def get_many(self, include_archived: bool) -> list[PlcEnvironment]:
        m = PlcEnvironmentOrmModel
        q = select(m)
        if not include_archived:
            q = q.where(m.archived.is_(False))
        rows = await self._db.scalars(q.order_by(m.name_key, m.id))
        return [_to_entity(r) for r in rows]

    async def get_live_by_name(self, name: str) -> PlcEnvironment | None:
        m = PlcEnvironmentOrmModel
        orm = await self._db.scalar(
            select(m).where(m.name_key == name.lower(), m.archived.is_(False)).limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_default(self) -> PlcEnvironment | None:
        m = PlcEnvironmentOrmModel
        orm = await self._db.scalar(
            select(m).where(m.is_default.is_(True), m.archived.is_(False)).order_by(m.id).limit(1)
        )
        return _to_entity(orm) if orm else None

    async def save(self, environment: PlcEnvironment) -> PlcEnvironment:
        values = _values(environment)
        if environment.id == 0:
            orm = PlcEnvironmentOrmModel(**values)
            self._db.add(orm)
        else:
            found = await self._db.get(PlcEnvironmentOrmModel, environment.id)
            if found is None:
                raise ValueError(f"PlcEnvironmentOrmModel id={environment.id} not found.")
            orm = found
            for key, value in values.items():
                setattr(orm, key, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return _to_entity(orm)

    async def clear_default_except(self, id: int) -> None:
        m = PlcEnvironmentOrmModel
        await self._db.execute(
            update(m).where(m.id != id, m.is_default.is_(True)).values(is_default=False)
        )
        await self._db.flush()
