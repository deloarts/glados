"""
Business rules for demand buckets, shared by the bought-item, made-item and
source-item families. No I/O. No ORM.

Buckets are display state, not business logic (see the bucket entities'
docstrings), so there is deliberately no ownership or MANAGE check anywhere
here, unlike the demand rules' update and cancel checks: any actor who holds
WRITE_DEMAND_ITEMS may create, rename or delete a bucket or assign one to any
demand, regardless of who created the bucket or the demand.
"""

import re

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission

_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class DemandBucketRules:
    @staticmethod
    def assert_can_write(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_DEMAND_ITEMS, "manage", "buckets")

    @staticmethod
    def normalize_name(name: str) -> str:
        return name.strip()

    @staticmethod
    def assert_valid_color(color: str) -> None:
        if not _COLOR_PATTERN.match(color):
            raise ValueError(f"Invalid bucket color {color!r}, expected format #RRGGBB.")
