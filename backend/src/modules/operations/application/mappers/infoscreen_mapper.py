"""
Converts Infoscreen entities to results, and request pages to the domain
value objects. Plain data is the bridge in both directions, so the domain
parser is the one place that decides what a valid page is.
"""

from typing import cast

from pydantic import TypeAdapter

from src.modules.operations.application.dto.infoscreen_dto import ColorMode
from src.modules.operations.application.dto.infoscreen_dto import DisplayScheduleDefaultResult
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenBar as InfoscreenBarDto
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenDisplaySchedule
from src.modules.operations.application.dto.infoscreen_dto import (
    InfoscreenPage as InfoscreenPageDto,
)
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenResult
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenTerminalRef
from src.modules.operations.application.dto.infoscreen_dto import ThemePreset
from src.modules.operations.domain.entities.infoscreen import Infoscreen
from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleDefault
from src.modules.operations.domain.value_objects.display_schedule import display_schedule_to_data
from src.modules.operations.domain.value_objects.display_schedule import parse_display_schedule
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenBar
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenPage
from src.modules.operations.domain.value_objects.infoscreen import bar_to_data
from src.modules.operations.domain.value_objects.infoscreen import pages_to_data
from src.modules.operations.domain.value_objects.infoscreen import parse_bar
from src.modules.operations.domain.value_objects.infoscreen import parse_pages
from src.modules.platform.application.mappers.user_mapper import UserMapper

_PAGES = TypeAdapter(list[InfoscreenPageDto])


def pages_from_dto(pages: list[InfoscreenPageDto]) -> list[InfoscreenPage]:
    """Validated domain pages of a request; raises InvalidInfoscreenConfigError."""
    return parse_pages([page.model_dump() for page in pages])


def bar_from_dto(bar: InfoscreenBarDto, where: str) -> InfoscreenBar:
    """A validated domain bar; raises InvalidInfoscreenConfigError."""
    return parse_bar(bar.model_dump(mode="json"), where)


def schedule_from_dto(schedule: InfoscreenDisplaySchedule | None) -> DisplaySchedule | None:
    """A validated domain schedule; raises InvalidInfoscreenConfigError."""
    return parse_display_schedule(schedule.model_dump() if schedule is not None else None)


def schedule_to_dto(schedule: DisplaySchedule | None) -> InfoscreenDisplaySchedule | None:
    data = display_schedule_to_data(schedule)
    return InfoscreenDisplaySchedule.model_validate(data) if data is not None else None


def bar_to_dto(bar: InfoscreenBar) -> InfoscreenBarDto:
    return InfoscreenBarDto.model_validate(bar_to_data(bar))


def pages_to_dto(pages: list[InfoscreenPage]) -> list[InfoscreenPageDto]:
    return _PAGES.validate_python(pages_to_data(pages))


def display_default_to_result(default: DisplayScheduleDefault) -> DisplayScheduleDefaultResult:
    return DisplayScheduleDefaultResult(
        display_schedule=schedule_to_dto(default.schedule),
        off_on_holidays=default.off_on_holidays,
    )


class InfoscreenMapper:
    @staticmethod
    def to_result(e: Infoscreen) -> InfoscreenResult:
        return InfoscreenResult(
            id=e.id,
            public_id=e.public_id,
            name=e.name,
            description=e.description,
            color_mode=cast(ColorMode, e.color_mode),
            theme_preset=cast(ThemePreset | None, e.theme_preset),
            primary_color=e.primary_color,
            rotation_seconds=e.rotation_seconds,
            show_banner=e.show_banner,
            show_header=e.show_header,
            header=bar_to_dto(e.header),
            show_footer=e.show_footer,
            footer=bar_to_dto(e.footer),
            pages=pages_to_dto(e.pages),
            language=e.language,
            display_schedule_mode=e.display_schedule_mode.value,
            display_schedule=schedule_to_dto(e.display_schedule),
            off_on_holidays=e.off_on_holidays,
            shown_on=[InfoscreenTerminalRef(id=ref.id, name=ref.name) for ref in e.shown_on],
            archived=e.archived,
            created=e.created,
            changed=e.changed,
            creator=UserMapper.to_public_result(e.creator) if e.creator else None,
            changed_by=UserMapper.to_public_result(e.changed_by) if e.changed_by else None,
        )
