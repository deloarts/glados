"""
Concrete implementation of IUserGroupRepository using SQLAlchemy. Members
are written through the group's relationship to the membership table.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_group_model import (
    UserGroupOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.entities.user_group import UserGroup
from src.modules.platform.domain.exceptions import UserGroupNotFoundError
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)


@lru_cache(maxsize=1)
def _group_load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences."""
    return (selectinload(UserGroupOrmModel.members), load_user(UserGroupOrmModel.changed_by))


def _orm_to_entity(orm: UserGroupOrmModel) -> UserGroup:
    return UserGroup(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        name=orm.name,
        description=orm.description,
        permissions=list(orm.permissions or []),
        creator_id=orm.creator_id,
        member_ids=sorted(m.id for m in orm.members),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def _entity_to_dict(group: UserGroup) -> dict[str, Any]:
    return {
        "created": group.created,
        "changed": group.changed,
        "changes": group.changes,
        "name": group.name,
        "description": group.description,
        "permissions": list(group.permissions),
        "creator_id": group.creator_id,
    }


class SqlAlchemyUserGroupRepository(IUserGroupRepository):
    def __init__(self, db: AsyncSession) -> None:
        """Writes only flush and the caller's unit of work commits them."""
        self._db = db

    async def list_all(self) -> list[UserGroup]:
        rows = await self._db.scalars(
            select(UserGroupOrmModel)
            .options(*_group_load_options())
            .order_by(func.lower(UserGroupOrmModel.name), UserGroupOrmModel.id)
        )
        return [_orm_to_entity(r) for r in rows.all()]

    async def get_by_id(self, id: int) -> UserGroup | None:
        orm = await self._db.scalar(by_id(UserGroupOrmModel, id, *_group_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_by_name_ci(self, name: str) -> UserGroup | None:
        orm = await self._db.scalar(
            select(UserGroupOrmModel)
            .options(*_group_load_options())
            .where(func.lower(UserGroupOrmModel.name) == name.strip().lower())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def _reload(self, id: int) -> UserGroupOrmModel:
        """The row again with its members and changer, after a flush that
        may have moved both."""
        return (
            await self._db.scalars(
                by_id(UserGroupOrmModel, id, *_group_load_options(), refresh=True)
            )
        ).one()

    async def save(self, group: UserGroup) -> UserGroup:
        members = (
            await load_by_ids(self._db, UserOrmModel, group.member_ids) if group.member_ids else []
        )
        if group.id == 0:
            # Members are assigned while the row is still new, see
            # SqlAlchemyUserRepository.save for why.
            orm = UserGroupOrmModel(**_entity_to_dict(group))
            orm.members = members
            self._db.add(orm)
            await self._db.flush()
            return _orm_to_entity(await self._reload(orm.id))
        existing = await self._db.scalar(
            by_id(UserGroupOrmModel, group.id, *_group_load_options(), refresh=True).limit(1)
        )
        if existing is None:
            raise ValueError(f"UserGroupOrmModel id={group.id} not found.")
        for key, value in _entity_to_dict(group).items():
            setattr(existing, key, value)
        existing.members = members
        await self._db.flush()
        return _orm_to_entity(await self._reload(group.id))

    async def delete(self, group: UserGroup) -> None:
        orm = await self._db.get(
            UserGroupOrmModel, group.id, options=[selectinload(UserGroupOrmModel.members)]
        )
        if orm is None:
            raise UserGroupNotFoundError(f"Group #{group.id} not found.")
        await self._db.delete(orm)
        await self._db.flush()
