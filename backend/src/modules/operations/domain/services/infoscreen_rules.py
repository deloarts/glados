"""
Business rules for infoscreens: who may write them and which screen
settings are valid. Pages and widget configs are validated by
value_objects.infoscreen.parse_pages. No I/O.
"""

from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_MAX
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_MIN
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenColorMode
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenThemePreset
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission

_MAX_PRIMARY_COLOR_LENGTH = 32


def assert_can_write(actor: User) -> None:
    assert_has_permission(actor, Permission.WRITE_INFOSCREENS, "write", "infoscreens")


def assert_settings_valid(
    *,
    color_mode: str,
    theme_preset: str | None,
    primary_color: str | None,
    rotation_seconds: int,
    language: str | None = None,
) -> None:
    """The look, language and timing of a screen. A None preset, primary
    colour or language falls back to the tenant default."""
    if color_mode not in InfoscreenColorMode.values():
        raise InvalidInfoscreenConfigError(
            f"color_mode must be one of {InfoscreenColorMode.values()}."
        )
    if theme_preset is not None and theme_preset not in InfoscreenThemePreset.values():
        raise InvalidInfoscreenConfigError(
            f"theme_preset must be one of {InfoscreenThemePreset.values()} or empty."
        )
    if primary_color is not None and (
        not primary_color.strip() or len(primary_color) > _MAX_PRIMARY_COLOR_LENGTH
    ):
        raise InvalidInfoscreenConfigError(
            f"primary_color must be 1 to {_MAX_PRIMARY_COLOR_LENGTH} characters or empty."
        )
    if language is not None and language not in Language.values():
        raise InvalidInfoscreenConfigError(f"language must be one of {Language.values()} or empty.")
    if not ROTATION_SECONDS_MIN <= rotation_seconds <= ROTATION_SECONDS_MAX:
        raise InvalidInfoscreenConfigError(
            f"rotation_seconds must be between {ROTATION_SECONDS_MIN} and {ROTATION_SECONDS_MAX}."
        )
