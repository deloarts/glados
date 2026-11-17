"""
The permission gate of the admin settings use cases. Reading any settings
page needs read:settings, changing one or running an admin operation needs
write:settings, and both raise the same message wherever they are checked.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission


class SettingsRules:
    @staticmethod
    def assert_can_read(actor: User) -> None:
        """Raises InsufficientPermissionsError unless the actor holds read:settings."""
        if not actor.has_permission(Permission.READ_SETTINGS):
            raise InsufficientPermissionsError("read:settings permission required.")

    @staticmethod
    def assert_can_write(actor: User) -> None:
        """Raises InsufficientPermissionsError unless the actor holds write:settings."""
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("write:settings permission required.")
