"""
HTTP request and response schemas for user groups.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.domain.services.user_group_rules import MAX_GROUP_DESCRIPTION_LENGTH
from src.modules.platform.domain.services.user_group_rules import MAX_GROUP_NAME_LENGTH


class SaveUserGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_GROUP_NAME_LENGTH)
    description: str = Field("", max_length=MAX_GROUP_DESCRIPTION_LENGTH)
    permissions: list[str] = []
    # The whole member list; users left out are removed from the group.
    member_ids: list[int] = []


class UserGroupResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    name: str
    description: str
    permissions: list[str]
    member_ids: list[int]
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
