"""
Shared CRUD logic for "labeled entity" domains: article groups and source
item types use it whole, fabrication and inspection methods use its label
helpers and archive/restore/get. All four are name + label_color +
label_font_color + description entities with an identical audit trail
(changelog); only the entity type, DTOs, permission rules and not-found
errors differ. Each use case class still owns its own constructor signature
and public `execute()` parameter names, only the mechanical body is shared
here.

`name` and `description` are maintained in every UI language at once
(`LocalizedText`). A name must have a text in the tenant's default language,
and no two live rows of one kind may show the same name in the same language
(`label_name_rules.py`); a clash raises `LabelTranslationConflictError`.
"""

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.catalogue.domain.errors import LabelTranslationConflictError
from src.modules.catalogue.domain.services.label_name_rules import find_name_clash
from src.modules.platform.application.services.command_changelog import entity_values
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.localized_text import require_language
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc


class _LabeledCommand(Protocol):
    name: dict[str, str]
    label_color: str
    label_font_color: str
    description: dict[str, str]

    def model_dump(self) -> dict[str, Any]: ...


class _HasModelDump(Protocol):
    def model_dump(self) -> dict[str, Any]: ...


class _LabeledEntity(Protocol):
    id: int
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool
    name: LocalizedText
    label_color: str
    label_font_color: str
    description: LocalizedText
    creator_id: int
    creator: User | None


TEntity = TypeVar("TEntity", bound=_LabeledEntity)
TFilter = TypeVar("TFilter", contravariant=True)


class _LabeledEntityRepo(Protocol[TEntity, TFilter]):
    async def get_by_id(self, id: int, /) -> TEntity | None: ...

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]: ...

    async def get_multi(self, filters: TFilter, /) -> tuple[int, list[TEntity]]: ...

    async def save(self, entity: TEntity, /) -> TEntity: ...

    async def next_sort_order(self) -> int: ...


class _LabeledEntityRules(Protocol):
    @staticmethod
    def assert_can_create(actor: User) -> None: ...

    @staticmethod
    def assert_can_update(actor: User) -> None: ...

    @staticmethod
    def assert_can_archive(actor: User) -> None: ...

    @staticmethod
    def assert_can_restore(actor: User) -> None: ...


@dataclass(frozen=True)
class LabeledEntitySpec(Generic[TEntity]):
    """
    Wording/wiring for one labeled-entity domain. `label` and `label_indefinite`
    drive both log messages and exception text, so they must match the
    original per-domain wording exactly (e.g. "article group" / "An article group").
    `entity_cls` is a factory rather than `type[TEntity]` so callers can pass
    the concrete dataclass without mypy demanding it structurally match
    `_LabeledEntity`'s Protocol constructor, which Protocols don't define.
    """

    entity_cls: Callable[..., TEntity]
    rules: type[_LabeledEntityRules]
    not_found_error: type[Exception]
    label: str
    label_indefinite: str


def shown_name(name: LocalizedText) -> str:
    """The name as a log line shows it, in its first language."""
    return name.resolve_in(())


async def checked_label(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    settings: IPlatformSettingsRepository,
    entity_id: int,
    raw_name: Mapping[str, str],
    raw_description: Mapping[str, str],
) -> tuple[LocalizedText, LocalizedText]:
    """The normalised name and description of a create (`entity_id` 0) or
    update. The name needs a text in the tenant's default language and must
    not clash with another live row's name in any language."""
    name = LocalizedText.of(raw_name)
    description = LocalizedText.of(raw_description)
    default_language = (await settings.get_general()).default_language
    require_language(name, default_language.value, f"{spec.label} name")
    await assert_no_name_clash(spec, repo, entity_id, name)
    return name, description


async def assert_no_name_clash(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    entity_id: int,
    name: LocalizedText,
) -> None:
    clash = find_name_clash(entity_id, name, await repo.get_live_names())
    if clash:
        raise LabelTranslationConflictError(
            f"{spec.label_indefinite} named {clash.text!r} already exists "
            f"in language {clash.language}."
        )


def label_changelog(
    entity: object,
    cmd: _HasModelDump,
    name: LocalizedText,
    description: LocalizedText,
) -> str:
    """The changelog entry of an update, one line per changed field, with
    the name and description compared per language (`name.deAT`). Call it
    before the command is applied to the entity."""
    new = cmd.model_dump()
    new.pop("expected_edit_version", None)
    old = entity_values(entity, new)
    new["name"], new["description"] = name, description
    return diff_changes(_per_language(old), _per_language(new))


def _per_language(values: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in values.items():
        if key in ("name", "description"):
            text = value if isinstance(value, LocalizedText) else LocalizedText(values=value)
            for language in sorted(text.values):
                flat[f"{key}.{language}"] = text.values[language]
        else:
            flat[key] = value
    return flat


async def create_labeled_entity(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    settings: IPlatformSettingsRepository,
    actor: User,
    cmd: _LabeledCommand,
) -> TEntity:
    spec.rules.assert_can_create(actor)
    name, description = await checked_label(spec, repo, settings, 0, cmd.name, cmd.description)

    now = now_utc()
    entity: TEntity = spec.entity_cls(
        id=0,
        created=now,
        changed=now,
        changes=append_changelog([], actor.full_name, f"{spec.label.capitalize()} created."),
        archived=False,
        name=name,
        label_color=cmd.label_color,
        label_font_color=cmd.label_font_color,
        description=description,
        creator_id=actor.id,
        creator=actor,
        sort_order=await repo.next_sort_order(),
    )
    saved = await repo.save(entity)
    log.info(f"Created {spec.label} {shown_name(saved.name)!r}, ID={saved.id}.")
    return saved


async def update_labeled_entity(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    settings: IPlatformSettingsRepository,
    actor: User,
    entity_id: int,
    cmd: _LabeledCommand,
) -> TEntity:
    spec.rules.assert_can_update(actor)

    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")

    name, description = await checked_label(
        spec, repo, settings, entity.id, cmd.name, cmd.description
    )
    changelog_entry = label_changelog(entity, cmd, name, description)

    entity.name = name
    entity.label_color = cmd.label_color
    entity.label_font_color = cmd.label_font_color
    entity.description = description
    entity.changed = now_utc()
    entity.changes = append_changelog(entity.changes, actor.full_name, changelog_entry)

    saved = await repo.save(entity)
    log.info(f"Updated {spec.label} {shown_name(saved.name)!r}, ID={saved.id}.")
    return saved


async def archive_labeled_entity(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    actor: User,
    entity_id: int,
) -> TEntity:
    """Idempotent: archiving an already-archived row is not an error, it
    still bumps `changed` and appends a changelog entry."""
    spec.rules.assert_can_archive(actor)

    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")

    entity.archived = True
    entity.changed = now_utc()
    entity.changes = append_changelog(
        entity.changes, actor.full_name, f"{spec.label.capitalize()} archived."
    )

    saved = await repo.save(entity)
    log.info(f"Archived {spec.label} {shown_name(saved.name)!r}, ID={saved.id}.")
    return saved


async def restore_labeled_entity(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    actor: User,
    entity_id: int,
) -> TEntity:
    """Idempotent, same as archive_labeled_entity. Restoring a row whose
    name, in any language, is now held by another live row raises
    `LabelTranslationConflictError` (409)."""
    spec.rules.assert_can_restore(actor)

    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")

    if entity.archived:
        await assert_no_name_clash(spec, repo, entity.id, entity.name)

    entity.archived = False
    entity.changed = now_utc()
    entity.changes = append_changelog(
        entity.changes, actor.full_name, f"{spec.label.capitalize()} restored."
    )

    saved = await repo.save(entity)
    log.info(f"Restored {spec.label} {shown_name(saved.name)!r}, ID={saved.id}.")
    return saved


async def get_labeled_entity(
    spec: LabeledEntitySpec[TEntity],
    repo: _LabeledEntityRepo[TEntity, TFilter],
    entity_id: int,
) -> TEntity:
    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")
    return entity


async def get_labeled_entities(
    repo: _LabeledEntityRepo[TEntity, TFilter],
    filters: TFilter,
) -> tuple[int, list[TEntity]]:
    return await repo.get_multi(filters)
