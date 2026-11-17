"""Converts UserGroup domain entities to result DTOs."""

from src.modules.platform.application.dto.user_group_dto import UserGroupResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.entities.user_group import UserGroup


class UserGroupMapper:
    @staticmethod
    def to_result(entity: UserGroup) -> UserGroupResult:
        return UserGroupResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            name=entity.name,
            description=entity.description,
            permissions=sorted(entity.permissions),
            member_ids=list(entity.member_ids),
            creator_id=entity.creator_id,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
