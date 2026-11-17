"""
Concrete implementation of IInfoscreenRepository using SQLAlchemy. Pages are
read through the domain parser, so a stored screen always comes back as
valid value objects; a row that no longer parses (edited by hand) comes
back with no pages, with the default bar, or always on, rather than
failing every read. The default display schedule is a singleton row next
to the screens.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.operations.adapters.outbound.persistence.models.infoscreen_model import (
    InfoscreenDisplayDefaultOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.models.infoscreen_model import (
    InfoscreenOrmModel,
)
from src.modules.operations.domain.entities.infoscreen import Infoscreen
from src.modules.operations.domain.entities.infoscreen import InfoscreenTerminalRef
from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleDefault
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.display_schedule import display_schedule_to_data
from src.modules.operations.domain.value_objects.display_schedule import parse_display_schedule
from src.modules.operations.domain.value_objects.infoscreen import DEFAULT_FOOTER
from src.modules.operations.domain.value_objects.infoscreen import DEFAULT_HEADER
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenBar
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenColorMode
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenPage
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenThemePreset
from src.modules.operations.domain.value_objects.infoscreen import bar_to_data
from src.modules.operations.domain.value_objects.infoscreen import pages_to_data
from src.modules.operations.domain.value_objects.infoscreen import parse_bar
from src.modules.operations.domain.value_objects.infoscreen import parse_pages
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SINGLETON_ID,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    upsert_singleton,
)
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.infrastructure.logging.logger import log


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences. Built on first call, after
    every model module is registered."""
    return (
        load_user(InfoscreenOrmModel.creator),
        load_user(InfoscreenOrmModel.changed_by),
        selectinload(InfoscreenOrmModel.terminals),
    )


def _pages(orm: InfoscreenOrmModel) -> list[InfoscreenPage]:
    try:
        return parse_pages(orm.pages or [])
    except InvalidInfoscreenConfigError:
        log.warning("Infoscreen #%s has stored pages that no longer parse; ignoring them.", orm.id)
        return []


def _bar(orm: InfoscreenOrmModel, raw: Any, default: InfoscreenBar) -> InfoscreenBar:
    if not isinstance(raw, dict):
        return default
    try:
        return parse_bar(raw)
    except InvalidInfoscreenConfigError:
        log.warning(
            "Infoscreen #%s has a stored bar that no longer parses; using the default.", orm.id
        )
        return default


def _schedule(orm: InfoscreenOrmModel) -> DisplaySchedule | None:
    try:
        return parse_display_schedule(orm.display_schedule)
    except InvalidInfoscreenConfigError:
        log.warning(
            "Infoscreen #%s has a stored display schedule that no longer parses; "
            "treating it as always on.",
            orm.id,
        )
        return None


def schedule_mode(raw: str | None) -> DisplayScheduleMode:
    """The stored mode; an unknown value follows the default schedule."""
    try:
        return DisplayScheduleMode(raw)
    except ValueError:
        return DisplayScheduleMode.DEFAULT


def _default_to_entity(orm: InfoscreenDisplayDefaultOrmModel | None) -> DisplayScheduleDefault:
    if orm is None:
        return DisplayScheduleDefault()
    try:
        schedule = parse_display_schedule(orm.display_schedule)
    except InvalidInfoscreenConfigError:
        log.warning("The default display schedule no longer parses; treating it as always on.")
        schedule = None
    return DisplayScheduleDefault(schedule=schedule, off_on_holidays=orm.off_on_holidays)


def _orm_to_entity(orm: InfoscreenOrmModel) -> Infoscreen:
    return Infoscreen(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=orm.name,
        description=orm.description,
        color_mode=InfoscreenColorMode(orm.color_mode),
        theme_preset=(
            InfoscreenThemePreset(orm.theme_preset) if orm.theme_preset is not None else None
        ),
        primary_color=orm.primary_color,
        rotation_seconds=orm.rotation_seconds,
        show_banner=orm.show_banner,
        pages=_pages(orm),
        show_header=orm.show_header,
        header=_bar(orm, orm.header, DEFAULT_HEADER),
        show_footer=orm.show_footer,
        footer=_bar(orm, orm.footer, DEFAULT_FOOTER),
        language=Language(orm.language) if orm.language is not None else None,
        display_schedule_mode=schedule_mode(orm.display_schedule_mode),
        display_schedule=_schedule(orm),
        off_on_holidays=orm.off_on_holidays,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        shown_on=[
            InfoscreenTerminalRef(id=t.id, name=t.name)
            for t in orm.terminals
            if t.status != TerminalStatus.REVOKED.value
        ],
    )


def _entity_to_dict(item: Infoscreen) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "archived": item.archived,
        "name": item.name,
        "description": item.description,
        "color_mode": item.color_mode.value,
        "theme_preset": item.theme_preset.value if item.theme_preset else None,
        "primary_color": item.primary_color,
        "rotation_seconds": item.rotation_seconds,
        "show_banner": item.show_banner,
        "pages": pages_to_data(item.pages),
        "show_header": item.show_header,
        "header": bar_to_data(item.header),
        "show_footer": item.show_footer,
        "footer": bar_to_data(item.footer),
        "language": item.language.value if item.language else None,
        "display_schedule_mode": item.display_schedule_mode.value,
        "display_schedule": display_schedule_to_data(item.display_schedule),
        "off_on_holidays": item.off_on_holidays,
        "creator_id": item.creator_id,
    }


class SqlAlchemyInfoscreenRepository:
    """Implements IInfoscreenRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> Infoscreen | None:
        orm = await self._db.scalar(by_id(InfoscreenOrmModel, id, *_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_all(self, *, include_archived: bool) -> list[Infoscreen]:
        q = select(InfoscreenOrmModel).options(*_load_options())
        if not include_archived:
            q = q.where(InfoscreenOrmModel.archived.is_(False))
        rows = await self._db.scalars(q.order_by(InfoscreenOrmModel.name, InfoscreenOrmModel.id))
        return [_orm_to_entity(r) for r in rows]

    async def get_live_by_name(self, name: str) -> Infoscreen | None:
        orm = await self._db.scalar(
            select(InfoscreenOrmModel)
            .where(
                func.lower(InfoscreenOrmModel.name) == name.strip().lower(),
                InfoscreenOrmModel.archived.is_(False),
            )
            .options(*_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def save(self, infoscreen: Infoscreen) -> Infoscreen:
        if infoscreen.id == 0:
            orm = InfoscreenOrmModel(**_entity_to_dict(infoscreen))
            self._db.add(orm)
            await self._db.flush()
            return _orm_to_entity(await self._reload(orm.id))
        existing = await self._db.scalar(by_id(InfoscreenOrmModel, infoscreen.id).limit(1))
        if existing is None:
            raise ValueError(f"InfoscreenOrmModel id={infoscreen.id} not found.")
        for key, value in _entity_to_dict(infoscreen).items():
            setattr(existing, key, value)
        await self._db.flush()
        return _orm_to_entity(await self._reload(infoscreen.id))

    async def get_display_default(self) -> DisplayScheduleDefault:
        """No row yet reads as always on."""
        return _default_to_entity(
            await self._db.get(InfoscreenDisplayDefaultOrmModel, SINGLETON_ID)
        )

    async def save_display_default(self, default: DisplayScheduleDefault) -> DisplayScheduleDefault:
        orm = await upsert_singleton(
            self._db,
            InfoscreenDisplayDefaultOrmModel,
            {
                "display_schedule": display_schedule_to_data(default.schedule),
                "off_on_holidays": default.off_on_holidays,
            },
        )
        return _default_to_entity(orm)

    async def _reload(self, id: int) -> InfoscreenOrmModel:
        return (
            await self._db.scalars(by_id(InfoscreenOrmModel, id, *_load_options(), refresh=True))
        ).one()
