"""
Commands and results for user groups.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.domain.services.user_group_rules import MAX_GROUP_DESCRIPTION_LENGTH
from src.modules.platform.domain.services.user_group_rules import MAX_GROUP_NAME_LENGTH


class SaveUserGroupCommand(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_GROUP_NAME_LENGTH)
    description: str = Field("", max_length=MAX_GROUP_DESCRIPTION_LENGTH)
    permissions: list[str] = []
    member_ids: list[int] = []


class UserGroupResult(ResultBase):
    created: datetime
    changed: datetime | None
    name: str
    description: str
    permissions: list[str]
    member_ids: list[int]
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResult | None
