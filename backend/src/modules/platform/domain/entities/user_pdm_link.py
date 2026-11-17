"""
Links one SOLIDWORKS PDM Web API user (UserInfo.UserId) to one Glados user.
Several PDM users may share a Glados user, but a PDM user id links to at most
one (a unique constraint). Only LinkPdmUsers, behind the admin PDM users
dialog, writes these rows. pdm_username is the vault name at link time, kept
for display only.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class UserPdmLink(Entity):
    user_id: int
    pdm_user_id: int
    pdm_username: str
    linked_at: datetime
