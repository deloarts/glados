"""
HTTP schemas for infoscreens and their feed. The widget configs, the page
model and the nested feed models are the application DTOs themselves, so
the builder, the preview and the display all read one definition; only the
top-level requests and responses are declared here.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.operations.application.dto.infoscreen_dto import ColorMode
from src.modules.operations.application.dto.infoscreen_dto import DisplayScheduleModeValue
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenBar
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenDisplaySchedule
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenPage
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenTerminalRef
from src.modules.operations.application.dto.infoscreen_dto import ThemePreset
from src.modules.operations.application.dto.infoscreen_dto import default_footer
from src.modules.operations.application.dto.infoscreen_dto import default_header
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedBanner
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedScreen
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenHoliday
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenWidgetData
from src.modules.operations.application.dto.terminal_dto import TerminalBroadcastMessage
from src.modules.operations.domain.value_objects.infoscreen import MAX_PAGES
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_DEFAULT
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_MAX
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_MIN
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.domain.value_objects.language import Language


class InfoscreenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color_mode: ColorMode = "dark"
    # None uses the tenant default.
    theme_preset: ThemePreset | None = None
    # None uses the tenant default.
    primary_color: str | None = Field(default=None, max_length=32)
    rotation_seconds: int = Field(
        default=ROTATION_SECONDS_DEFAULT, ge=ROTATION_SECONDS_MIN, le=ROTATION_SECONDS_MAX
    )
    show_banner: bool = True
    show_header: bool = True
    header: InfoscreenBar = Field(default_factory=default_header)
    show_footer: bool = False
    footer: InfoscreenBar = Field(default_factory=default_footer)
    pages: list[InfoscreenPage] = Field(default_factory=list, max_length=MAX_PAGES)
    # None shows the built-in copy in the tenant's default language.
    language: Language | None = None
    # Which schedule the displays follow; the screen's own only in "own".
    display_schedule_mode: DisplayScheduleModeValue = "default"
    # None keeps the displays on all the time.
    display_schedule: InfoscreenDisplaySchedule | None = None
    off_on_holidays: bool = False


class InfoscreenUpdateRequest(BaseModel):
    """Only the fields sent change; an explicit null clears description,
    theme_preset, primary_color, language or display_schedule."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    color_mode: ColorMode | None = None
    theme_preset: ThemePreset | None = None
    primary_color: str | None = Field(default=None, max_length=32)
    rotation_seconds: int | None = Field(
        default=None, ge=ROTATION_SECONDS_MIN, le=ROTATION_SECONDS_MAX
    )
    show_banner: bool | None = None
    show_header: bool | None = None
    header: InfoscreenBar | None = None
    show_footer: bool | None = None
    footer: InfoscreenBar | None = None
    pages: list[InfoscreenPage] | None = Field(default=None, max_length=MAX_PAGES)
    language: Language | None = None
    display_schedule_mode: DisplayScheduleModeValue | None = None
    display_schedule: InfoscreenDisplaySchedule | None = None
    off_on_holidays: bool | None = None


class InfoscreenResponse(EntityResponse):
    name: str
    description: str | None
    color_mode: ColorMode
    theme_preset: ThemePreset | None
    primary_color: str | None
    rotation_seconds: int
    show_banner: bool
    show_header: bool
    header: InfoscreenBar
    show_footer: bool
    footer: InfoscreenBar
    pages: list[InfoscreenPage]
    language: Language | None
    display_schedule_mode: DisplayScheduleModeValue
    display_schedule: InfoscreenDisplaySchedule | None
    off_on_holidays: bool
    shown_on: list[InfoscreenTerminalRef]
    archived: bool
    created: datetime
    changed: datetime | None
    creator: PublicUserResponse | None
    changed_by: PublicUserResponse | None


class DisplayScheduleDefaultRequest(BaseModel):
    """The default display schedule of every screen in the "default" mode.
    None keeps their displays on all the time."""

    display_schedule: InfoscreenDisplaySchedule | None = None
    off_on_holidays: bool = False


class DisplayScheduleDefaultResponse(ResponseModel):
    display_schedule: InfoscreenDisplaySchedule | None
    off_on_holidays: bool


class InfoscreenFeedResponse(ResponseModel):
    """`widgets[p][s]` is the data for `infoscreen.pages[p].slots[s]`."""

    infoscreen: InfoscreenFeedScreen
    widgets: list[list[InfoscreenWidgetData | None]]
    banner: InfoscreenFeedBanner | None
    # Filled when a shown bar has the next_holiday item.
    next_holiday: InfoscreenHoliday | None
    generated_at: datetime
    backend_version: str
    # The tenant's default timezone (IANA name); the display draws every time
    # and date in it, whatever zone the device itself is set to.
    timezone: str
    # The screen's language, or the tenant's default language when it has
    # none; the display shows its built-in copy and formats in it.
    language: Language
    # The newest active message to terminals that reaches the display (the
    # preview: one to every terminal or picking this screen). No author.
    broadcast: TerminalBroadcastMessage | None


class WeatherPlaceResponse(ResponseModel):
    name: str
    region: str | None
    country_code: str
    latitude: float
    longitude: float
