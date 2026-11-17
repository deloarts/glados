"""
An infoscreen: a screen definition that terminals show without anyone
touching them. It holds the look (colour mode, theme preset, primary
colour), how long each page stays up, whether the global banner is shown,
the header and footer bars, its pages with one widget config per slot, the
language its built-in copy is shown in (None for the tenant default), and
the display schedule every terminal showing it follows. One screen can be
shown on many terminals; a terminal shows at most one screen.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.infoscreen import DEFAULT_FOOTER
from src.modules.operations.domain.value_objects.infoscreen import DEFAULT_HEADER
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenBar
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenColorMode
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenPage
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenThemePreset
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.language import Language
from src.shared_kernel.domain.entities.base import Entity


@dataclass(frozen=True)
class InfoscreenTerminalRef:
    """A terminal showing the screen, for its read-only "shown on" list."""

    id: int
    name: str | None


@dataclass
class Infoscreen(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    description: str | None
    color_mode: InfoscreenColorMode
    theme_preset: InfoscreenThemePreset | None  # None is the tenant default
    primary_color: str | None  # None is the tenant default
    rotation_seconds: int
    show_banner: bool
    pages: list[InfoscreenPage]

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    # ── Bars above and below the pages ────────────────────────────────
    show_header: bool = True
    header: InfoscreenBar = DEFAULT_HEADER
    show_footer: bool = False
    footer: InfoscreenBar = DEFAULT_FOOTER

    # ── Language and display schedule ─────────────────────────────────
    language: Language | None = None  # None is the tenant default
    # Which schedule the displays follow; the own one below only in OWN.
    display_schedule_mode: DisplayScheduleMode = DisplayScheduleMode.DEFAULT
    # None means always on.
    display_schedule: DisplaySchedule | None = None
    # Displays stay off on tenant holidays, whatever the schedule says.
    off_on_holidays: bool = False

    # ── Denormalized (read-only, populated by repository mapper) ──────
    shown_on: list[InfoscreenTerminalRef] = field(default_factory=list)
