"""
Commands and results for infoscreens, and the widget config models a page
slot holds. The widget configs and pages are shared by the create and update
commands, the screen result and the feed, so they keep their defaulted fields
optional. The domain value objects (value_objects/infoscreen.py) validate
them again on every write, which is where the slot count of a layout is
checked.
"""

from datetime import datetime
from typing import Annotated
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.operations.domain.value_objects.display_schedule import MAX_WINDOWS_PER_DAY
from src.modules.operations.domain.value_objects.infoscreen import DELIVERIES_HORIZON_MAX
from src.modules.operations.domain.value_objects.infoscreen import DELIVERIES_HORIZON_MIN
from src.modules.operations.domain.value_objects.infoscreen import DETAIL_NEXT_COUNT_MAX
from src.modules.operations.domain.value_objects.infoscreen import DETAIL_NEXT_COUNT_MIN
from src.modules.operations.domain.value_objects.infoscreen import EXTERNAL_WORK_HORIZON_MAX
from src.modules.operations.domain.value_objects.infoscreen import EXTERNAL_WORK_HORIZON_MIN
from src.modules.operations.domain.value_objects.infoscreen import LOTS_HORIZON_MAX
from src.modules.operations.domain.value_objects.infoscreen import LOTS_HORIZON_MIN
from src.modules.operations.domain.value_objects.infoscreen import MAX_BAR_TEXT_LENGTH
from src.modules.operations.domain.value_objects.infoscreen import MAX_IDS_PER_WIDGET
from src.modules.operations.domain.value_objects.infoscreen import MAX_MESSAGE_LENGTH
from src.modules.operations.domain.value_objects.infoscreen import MAX_PAGES
from src.modules.operations.domain.value_objects.infoscreen import MAX_PLACE_NAME_LENGTH
from src.modules.operations.domain.value_objects.infoscreen import MAX_TITLE_LENGTH
from src.modules.operations.domain.value_objects.infoscreen import NEXT_COUNT_MAX
from src.modules.operations.domain.value_objects.infoscreen import NEXT_COUNT_MIN
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_DEFAULT
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_MAX
from src.modules.operations.domain.value_objects.infoscreen import ROTATION_SECONDS_MIN
from src.modules.operations.domain.value_objects.infoscreen import WEATHER_DAYS_MAX
from src.modules.operations.domain.value_objects.infoscreen import WEATHER_DAYS_MIN
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenBarItem
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.domain.value_objects.language import Language

ColorMode = Literal["dark", "light"]
ThemePreset = Literal["Aura", "Lara", "Material", "Nora"]
# Which schedule a screen's displays follow, a DisplayScheduleMode value.
DisplayScheduleModeValue = Literal["default", "own", "always_on"]
PageLayout = Literal[
    "full",
    "two_columns",
    "main_side",
    "grid_2x2",
    "two_rows",
    "three_rows",
    "grid_2x3",
    "grid_3x2",
]
MessageSeverity = Literal["none", "info", "success", "warning", "danger"]
TextAlign = Literal["left", "center", "right"]
VerticalAlign = Literal["top", "middle", "bottom"]


def _title() -> Any:
    return Field(default=None, max_length=MAX_TITLE_LENGTH)


def _ids() -> Any:
    return Field(default_factory=list, max_length=MAX_IDS_PER_WIDGET)


# ── Widget configs ────────────────────────────────────────────────────


class MachineBoardWidgetConfig(BaseModel):
    type: Literal["machine_board"]
    title: str | None = _title()
    machine_ids: list[int] = _ids()
    pool_ids: list[int] = _ids()
    next_count: int = Field(default=3, ge=NEXT_COUNT_MIN, le=NEXT_COUNT_MAX)


class LotsDueWidgetConfig(BaseModel):
    type: Literal["lots_due"]
    title: str | None = _title()
    horizon_days: int = Field(default=7, ge=LOTS_HORIZON_MIN, le=LOTS_HORIZON_MAX)
    pool_ids: list[int] = _ids()
    show_customer: bool = False


class LateLotsWidgetConfig(BaseModel):
    type: Literal["late_lots"]
    title: str | None = _title()
    show_customer: bool = False


class QaQueueWidgetConfig(BaseModel):
    type: Literal["qa_queue"]
    title: str | None = _title()


class DeliveriesExpectedWidgetConfig(BaseModel):
    type: Literal["deliveries_expected"]
    title: str | None = _title()
    horizon_days: int = Field(default=0, ge=DELIVERIES_HORIZON_MIN, le=DELIVERIES_HORIZON_MAX)
    show_overdue: bool = False


class ExternalWorkWidgetConfig(BaseModel):
    type: Literal["external_work"]
    title: str | None = _title()
    horizon_days: int = Field(default=7, ge=EXTERNAL_WORK_HORIZON_MIN, le=EXTERNAL_WORK_HORIZON_MAX)
    show_overdue: bool = True
    fabrication_method_ids: list[int] = _ids()
    only_with_supplier: bool = False
    layout: Literal["days", "suppliers"] = "days"


class MessageWidgetConfig(BaseModel):
    """A text the screen shows as Markdown, stored as typed."""

    type: Literal["message"]
    title: str | None = _title()
    text: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    severity: MessageSeverity = "info"
    text_align: TextAlign = "left"
    vertical_align: VerticalAlign = "middle"


class ClockWidgetConfig(BaseModel):
    type: Literal["clock"]
    title: str | None = _title()
    show_date: bool = True
    show_next_holiday: bool = False
    show_seconds: bool = False
    style: Literal["digital", "analogue", "binary"] = "digital"


class WeatherWidgetConfig(BaseModel):
    """A town picked by name; the coordinates are its centre, which the
    domain rounds to two decimals."""

    type: Literal["weather"]
    title: str | None = _title()
    location_name: str = Field(..., min_length=1, max_length=MAX_PLACE_NAME_LENGTH)
    region: str | None = Field(default=None, max_length=MAX_PLACE_NAME_LENGTH)
    country_code: str = Field(..., min_length=2, max_length=2)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    days: int = Field(default=3, ge=WEATHER_DAYS_MIN, le=WEATHER_DAYS_MAX)
    show_wind: bool = False


class ProductsWidgetConfig(BaseModel):
    type: Literal["products"]
    title: str | None = _title()
    show_projects: bool = False
    show_customer: bool = False


class ProjectsWidgetConfig(BaseModel):
    type: Literal["projects"]
    title: str | None = _title()
    show_customer: bool = False


class MachineDetailWidgetConfig(BaseModel):
    type: Literal["machine_detail"]
    title: str | None = _title()
    machine_id: int = Field(..., gt=0)
    next_count: int = Field(default=3, ge=DETAIL_NEXT_COUNT_MIN, le=DETAIL_NEXT_COUNT_MAX)
    show_drawing: bool = True
    show_customer: bool = False


InfoscreenWidgetConfig = Annotated[
    MachineBoardWidgetConfig
    | LotsDueWidgetConfig
    | LateLotsWidgetConfig
    | QaQueueWidgetConfig
    | DeliveriesExpectedWidgetConfig
    | MessageWidgetConfig
    | ClockWidgetConfig
    | WeatherWidgetConfig
    | ProductsWidgetConfig
    | ProjectsWidgetConfig
    | MachineDetailWidgetConfig
    | ExternalWorkWidgetConfig,
    Field(discriminator="type"),
]


class InfoscreenPage(BaseModel):
    """One page; `slots` holds one entry per position of the layout."""

    layout: PageLayout
    slots: list[InfoscreenWidgetConfig | None]


class InfoscreenBar(BaseModel):
    """A header or footer bar with a left, center and right area, each
    listing its items left to right. An item appears at most once across the
    bar; `text` is what the `text` item shows."""

    left: list[InfoscreenBarItem] = Field(default_factory=list)
    center: list[InfoscreenBarItem] = Field(default_factory=list)
    right: list[InfoscreenBarItem] = Field(default_factory=list)
    text: str | None = Field(default=None, max_length=MAX_BAR_TEXT_LENGTH)


def default_header() -> InfoscreenBar:
    return InfoscreenBar(
        left=[InfoscreenBarItem.LOGO, InfoscreenBarItem.TITLE], right=[InfoscreenBarItem.CLOCK]
    )


def default_footer() -> InfoscreenBar:
    return InfoscreenBar(right=[InfoscreenBarItem.LAST_UPDATED])


# ── Display schedule ──────────────────────────────────────────────────

_HHMM = r"^\d{2}:\d{2}$"


class InfoscreenDisplayWindow(BaseModel):
    """An on-window of one day in the tenant timezone. `end` may be 24:00,
    the following midnight."""

    start: str = Field(..., pattern=_HHMM)
    end: str = Field(..., pattern=_HHMM)


def _windows() -> Any:
    return Field(default_factory=list, max_length=MAX_WINDOWS_PER_DAY)


class InfoscreenDisplaySchedule(BaseModel):
    """The on-windows of every weekday; a day without windows is off."""

    monday: list[InfoscreenDisplayWindow] = _windows()
    tuesday: list[InfoscreenDisplayWindow] = _windows()
    wednesday: list[InfoscreenDisplayWindow] = _windows()
    thursday: list[InfoscreenDisplayWindow] = _windows()
    friday: list[InfoscreenDisplayWindow] = _windows()
    saturday: list[InfoscreenDisplayWindow] = _windows()
    sunday: list[InfoscreenDisplayWindow] = _windows()


# ── Commands (inbound) ────────────────────────────────────────────────


class CreateInfoscreenCommand(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color_mode: ColorMode = "dark"
    theme_preset: ThemePreset | None = None
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
    language: Language | None = None
    display_schedule_mode: DisplayScheduleModeValue = "default"
    display_schedule: InfoscreenDisplaySchedule | None = None
    off_on_holidays: bool = False


class UpdateInfoscreenCommand(BaseModel):
    """Partial update. `fields_set` names the fields the request sent, so an
    explicit null clears a nullable field while an absent one keeps it."""

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
    fields_set: set[str] = Field(default_factory=set)


class SetDisplayScheduleDefaultCommand(BaseModel):
    """The default display schedule; None keeps the displays on."""

    display_schedule: InfoscreenDisplaySchedule | None = None
    off_on_holidays: bool = False


# ── Results (outbound) ────────────────────────────────────────────────


class DisplayScheduleDefaultResult(ResultModel):
    display_schedule: InfoscreenDisplaySchedule | None
    off_on_holidays: bool


class InfoscreenTerminalRef(ResultModel):
    id: int
    name: str | None


class InfoscreenResult(ResultBase):
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
    creator: PublicUserResult | None
    changed_by: PublicUserResult | None


class WeatherPlaceResult(ResultModel):
    """A town the weather widget may show, with its centre rounded to two
    decimals."""

    name: str
    region: str | None
    country_code: str
    latitude: float
    longitude: float
