"""
Use cases for infoscreen definitions: list and read (open to every signed-in
user), create, update, archive and restore (write:infoscreens). An archived
screen keeps working on the terminals that show it; it can only no longer
be assigned. Names are unique among live screens.
"""

from typing import Any

from src.modules.operations.application.dto.infoscreen_dto import CreateInfoscreenCommand
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenResult
from src.modules.operations.application.dto.infoscreen_dto import UpdateInfoscreenCommand
from src.modules.operations.application.mappers.infoscreen_mapper import InfoscreenMapper
from src.modules.operations.application.mappers.infoscreen_mapper import bar_from_dto
from src.modules.operations.application.mappers.infoscreen_mapper import pages_from_dto
from src.modules.operations.application.mappers.infoscreen_mapper import schedule_from_dto
from src.modules.operations.domain.entities.infoscreen import Infoscreen
from src.modules.operations.domain.errors import InfoscreenNameTakenError
from src.modules.operations.domain.errors import InfoscreenNotFoundError
from src.modules.operations.domain.services import infoscreen_rules
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenColorMode
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenThemePreset
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc

_TRACKED_FIELDS = (
    "name",
    "description",
    "color_mode",
    "theme_preset",
    "primary_color",
    "rotation_seconds",
    "show_banner",
    "show_header",
    "show_footer",
    "display_schedule_mode",
    "off_on_holidays",
)
_NULLABLE_FIELDS = frozenset({"description", "theme_preset", "primary_color"})


def _theme_preset(value: str | None) -> InfoscreenThemePreset | None:
    return InfoscreenThemePreset(value) if value is not None else None


def _parsed(field_name: str, value: Any) -> Any:
    """A tracked field's command value as the entity holds it, the colour
    mode and the theme preset as their enum members."""
    if field_name == "color_mode":
        return InfoscreenColorMode(value)
    if field_name == "theme_preset":
        return _theme_preset(value)
    if field_name == "display_schedule_mode":
        return DisplayScheduleMode(value)
    return value


def _not_found(infoscreen_id: int) -> InfoscreenNotFoundError:
    return InfoscreenNotFoundError(f"Infoscreen #{infoscreen_id} not found.")


async def _assert_name_free(
    repo: IInfoscreenRepository, name: str, own_id: int | None = None
) -> None:
    existing = await repo.get_live_by_name(name)
    if existing is not None and existing.id != own_id:
        raise InfoscreenNameTakenError(f"An infoscreen named {name!r} already exists.")


class GetInfoscreens:
    def __init__(self, infoscreen_repo: IInfoscreenRepository) -> None:
        self._screens = infoscreen_repo

    async def execute(self, *, include_archived: bool) -> list[InfoscreenResult]:
        screens = await self._screens.get_all(include_archived=include_archived)
        return [InfoscreenMapper.to_result(s) for s in screens]


class GetInfoscreen:
    def __init__(self, infoscreen_repo: IInfoscreenRepository) -> None:
        self._screens = infoscreen_repo

    async def execute(self, infoscreen_id: int) -> InfoscreenResult:
        screen = found_or_raise(
            await self._screens.get_by_id(infoscreen_id),
            InfoscreenNotFoundError,
            f"Infoscreen #{infoscreen_id} not found.",
        )
        return InfoscreenMapper.to_result(screen)


class CreateInfoscreen:
    def __init__(self, infoscreen_repo: IInfoscreenRepository, *, uow: IUnitOfWork) -> None:
        self._screens = infoscreen_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateInfoscreenCommand) -> InfoscreenResult:
        infoscreen_rules.assert_can_write(actor)
        language = cmd.language.value if cmd.language is not None else None
        infoscreen_rules.assert_settings_valid(
            color_mode=cmd.color_mode,
            theme_preset=cmd.theme_preset,
            primary_color=cmd.primary_color,
            rotation_seconds=cmd.rotation_seconds,
            language=language,
        )
        schedule = schedule_from_dto(cmd.display_schedule)
        pages = pages_from_dto(cmd.pages)
        header = bar_from_dto(cmd.header, "Header")
        footer = bar_from_dto(cmd.footer, "Footer")
        name = cmd.name.strip()
        await _assert_name_free(self._screens, name)

        now = now_utc()
        saved = await self._screens.save(
            Infoscreen(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog([], actor.full_name, "Infoscreen created."),
                archived=False,
                name=name,
                description=cmd.description,
                color_mode=InfoscreenColorMode(cmd.color_mode),
                theme_preset=_theme_preset(cmd.theme_preset),
                primary_color=cmd.primary_color,
                rotation_seconds=cmd.rotation_seconds,
                show_banner=cmd.show_banner,
                show_header=cmd.show_header,
                header=header,
                show_footer=cmd.show_footer,
                footer=footer,
                pages=pages,
                language=cmd.language,
                display_schedule_mode=DisplayScheduleMode(cmd.display_schedule_mode),
                display_schedule=schedule,
                off_on_holidays=cmd.off_on_holidays,
                creator_id=actor.id,
            )
        )
        await self._uow.commit()
        log.info(f"Created infoscreen {saved.name!r}, ID={saved.id}.")
        return InfoscreenMapper.to_result(saved)


class UpdateInfoscreen:
    def __init__(self, infoscreen_repo: IInfoscreenRepository, *, uow: IUnitOfWork) -> None:
        self._screens = infoscreen_repo
        self._uow = uow

    async def execute(
        self, actor: User, infoscreen_id: int, cmd: UpdateInfoscreenCommand
    ) -> InfoscreenResult:
        infoscreen_rules.assert_can_write(actor)
        screen = found_or_raise(
            await self._screens.get_by_id(infoscreen_id),
            InfoscreenNotFoundError,
            f"Infoscreen #{infoscreen_id} not found.",
        )
        old = {f: getattr(screen, f) for f in _TRACKED_FIELDS}
        for f in _TRACKED_FIELDS:
            value = getattr(cmd, f)
            if value is not None or (f in _NULLABLE_FIELDS and f in cmd.fields_set):
                setattr(screen, f, _parsed(f, value))
        if cmd.name is not None:
            screen.name = cmd.name.strip()
            if not screen.archived:
                await _assert_name_free(self._screens, screen.name, own_id=screen.id)
        old["language"] = screen.language
        if "language" in cmd.fields_set:
            screen.language = cmd.language
        infoscreen_rules.assert_settings_valid(
            color_mode=screen.color_mode,
            theme_preset=screen.theme_preset,
            primary_color=screen.primary_color,
            rotation_seconds=screen.rotation_seconds,
            language=screen.language,
        )
        summary = diff_changes(
            old,
            {**{f: getattr(screen, f) for f in _TRACKED_FIELDS}, "language": screen.language},
            heading="Infoscreen updated:",
        )
        updated: list[str] = []
        if "display_schedule" in cmd.fields_set:
            screen.display_schedule = schedule_from_dto(cmd.display_schedule)
            updated.append("Display schedule updated.")
        if cmd.pages is not None:
            screen.pages = pages_from_dto(cmd.pages)
            updated.append("Pages updated.")
        if cmd.header is not None:
            screen.header = bar_from_dto(cmd.header, "Header")
            updated.append("Header updated.")
        if cmd.footer is not None:
            screen.footer = bar_from_dto(cmd.footer, "Footer")
            updated.append("Footer updated.")
        if updated:
            lines = [] if summary == "No changes." else [summary]
            summary = "\n".join([*lines, *updated])

        screen.changed = now_utc()
        screen.changes = append_changelog(screen.changes, actor.full_name, summary)
        saved = await self._screens.save(screen)
        await self._uow.commit()
        log.info(f"Updated infoscreen {saved.name!r}, ID={saved.id}.")
        return InfoscreenMapper.to_result(saved)


class SetInfoscreenArchived:
    """Archive or restore; idempotent like every archive and restore route.
    Restoring answers 409 when a live screen now holds the same name."""

    def __init__(self, infoscreen_repo: IInfoscreenRepository, *, uow: IUnitOfWork) -> None:
        self._screens = infoscreen_repo
        self._uow = uow

    async def execute(self, actor: User, infoscreen_id: int, *, archived: bool) -> InfoscreenResult:
        infoscreen_rules.assert_can_write(actor)

        async def _before_save(screen: Infoscreen) -> None:
            if not archived and screen.archived:
                await _assert_name_free(self._screens, screen.name, own_id=screen.id)
            screen.changed = now_utc()
            screen.changes = append_changelog(
                screen.changes,
                actor.full_name,
                "Infoscreen archived." if archived else "Infoscreen restored.",
            )

        saved = await set_archived(
            entity_id=infoscreen_id,
            archived=archived,
            load=self._screens.get_by_id,
            not_found=_not_found,
            save=self._screens.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(
            f"{'Archived' if archived else 'Restored'} infoscreen {saved.name!r}, ID={saved.id}."
        )
        return InfoscreenMapper.to_result(saved)
