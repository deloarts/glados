"""
An admin settings stand-in that answers only the general settings, for the
`settings` of a SchedulingRepos or a labeled catalogue use case in a unit
test. The scheduling reads take the tenant's timezone from it, and the
default UTC keeps a test's days the plain UTC days. The label use cases take
the tenant's default language from it, which a name must always carry.
"""

from types import SimpleNamespace

from src.modules.platform.domain.value_objects.language import Language


class TenantSettings:
    """Answers get_general with the tenant timezone `timezone` and the
    default language `default_language`."""

    def __init__(self, timezone: str = "UTC", default_language: Language = Language.enGB) -> None:
        self.timezone = timezone
        self.default_language = default_language

    async def get_general(self) -> SimpleNamespace:
        return SimpleNamespace(
            default_timezone=self.timezone, default_language=self.default_language
        )
