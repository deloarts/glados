"""
Where a user lands right after signing in, when nothing more specific (an
explicit `redirect` query param) says otherwise. A closed set mirroring the
sidebar's top-level entries, not a free-form path: a stored arbitrary route
could point at a page removed in a later release, or off-app entirely.

Per-user only: there is deliberately no tenant-wide default here, unlike
Language/Timezone/DateFormat, which all have one on AdminGeneralSettings.
Every account starts on "dashboard" until it changes its own preference.

Presentation only, same as DateFormat: nothing server-side ever branches on
this value, it is read back by the frontend's own post-login routing.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class StartPage(StrValueEnum):
    DASHBOARD = "dashboard"
    TODO = "todo"
    WORKSPACE = "workspace"
    CATALOGUE = "catalogue"
    PROCUREMENT = "procurement"
    PRODUCTION = "production"
    RESOURCES = "resources"
    TOOLS = "tools"

    @classmethod
    def default(cls) -> "StartPage":
        """Dashboard, matching every account's behaviour before this
        preference existed."""
        return cls.DASHBOARD
