"""
OpenVue theming model: preset (design system), surface (neutral palette) and
primary (accent palette).
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ThemePreset(StrValueEnum):
    """OpenVue built-in design presets."""

    Aura = "Aura"
    Lara = "Lara"
    Material = "Material"
    Nora = "Nora"

    @classmethod
    def default(cls) -> "ThemePreset":
        return cls.Aura


@unique
class ThemeSurface(StrValueEnum):
    """Neutral surface palettes of the OpenVue theme."""

    glados = "glados"
    slate = "slate"
    gray = "gray"
    zinc = "zinc"
    neutral = "neutral"
    stone = "stone"

    @classmethod
    def default(cls) -> "ThemeSurface":
        return cls.glados


@unique
class ThemePrimary(StrValueEnum):
    """Accent colour palettes of the OpenVue theme."""

    glados = "glados"
    noir = "noir"
    soul = "soul"
    emerald = "emerald"
    green = "green"
    lime = "lime"
    red = "red"
    orange = "orange"
    amber = "amber"
    yellow = "yellow"
    teal = "teal"
    cyan = "cyan"
    sky = "sky"
    blue = "blue"
    indigo = "indigo"
    violet = "violet"
    purple = "purple"
    fuchsia = "fuchsia"
    pink = "pink"
    rose = "rose"

    @classmethod
    def default(cls) -> "ThemePrimary":
        return cls.glados
