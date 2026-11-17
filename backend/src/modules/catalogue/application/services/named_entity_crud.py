"""
Shared CRUD logic for labeled entities whose name and description are one
plain string, product families today. They have the name + label_color +
label_font_color + description shape and audit trail of the localized
labeled entities in labeled_entity_crud.py, but a single name that is unique
among live rows. Each use case class still owns its own constructor
signature and public `execute()` parameter names, only the mechanical body
is shared here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class _NamedCommand(Protocol):
    name: str
    label_color: str
    label_font_color: str
    description: str

    def model_dump(self) -> dict[str, Any]: ...


class _NamedEntity(Protocol):
    id: int
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool
    name: str
    label_color: str
    label_font_color: str
    description: str
    creator_id: int
    creator: User | None


TEntity = TypeVar("TEntity", bound=_NamedEntity)
TFilter = TypeVar("TFilter", contravariant=True)


class _NamedEntityRepo(Protocol[TEntity, TFilter]):
    async def get_by_id(self, id: int, /) -> TEntity | None: ...

    async def get_by_name(self, name: str, /) -> TEntity | None: ...

    async def get_multi(self, filters: TFilter, /) -> tuple[int, list[TEntity]]: ...

    async def save(self, entity: TEntity, /) -> TEntity: ...

    async def next_sort_order(self) -> int: ...


class _NamedEntityRules(Protocol):
    @staticmethod
    def assert_can_create(actor: User) -> None: ...

    @staticmethod
    def assert_can_update(actor: User) -> None: ...

    @staticmethod
    def assert_can_archive(actor: User) -> None: ...

    @staticmethod
    def assert_can_restore(actor: User) -> None: ...


@dataclass(frozen=True)
class NamedEntitySpec(Generic[TEntity]):
    """
    Wording/wiring for one labeled-entity domain. `label` and `label_indefinite`
    drive both log messages and exception text, so they must match the
    original per-domain wording exactly (e.g. "article group" / "An article group").
    `entity_cls` is a factory rather than `type[TEntity]` so callers can pass
    the concrete dataclass without mypy demanding it structurally match
    `_NamedEntity`'s Protocol constructor, which Protocols don't define.
    """

    entity_cls: Callable[..., TEntity]
    rules: type[_NamedEntityRules]
    not_found_error: type[Exception]
    already_exists_error: type[Exception]
    label: str
    label_indefinite: str


async def create_named_entity(
    spec: NamedEntitySpec[TEntity],
    repo: _NamedEntityRepo[TEntity, TFilter],
    actor: User,
    cmd: _NamedCommand,
) -> TEntity:
    spec.rules.assert_can_create(actor)

    if await repo.get_by_name(cmd.name):
        raise spec.already_exists_error(
            f"{spec.label_indefinite} named {cmd.name!r} already exists."
        )

    now = now_utc()
    entity: TEntity = spec.entity_cls(
        id=0,
        created=now,
        changed=now,
        changes=append_changelog([], actor.full_name, f"{spec.label.capitalize()} created."),
        archived=False,
        name=cmd.name,
        label_color=cmd.label_color,
        label_font_color=cmd.label_font_color,
        description=cmd.description,
        creator_id=actor.id,
        creator=actor,
        sort_order=await repo.next_sort_order(),
    )
    saved = await repo.save(entity)
    log.info(f"Created {spec.label} {saved.name!r}, ID={saved.id}.")
    return saved


async def update_named_entity(
    spec: NamedEntitySpec[TEntity],
    repo: _NamedEntityRepo[TEntity, TFilter],
    actor: User,
    entity_id: int,
    cmd: _NamedCommand,
) -> TEntity:
    spec.rules.assert_can_update(actor)

    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")

    if cmd.name != entity.name:
        existing = await repo.get_by_name(cmd.name)
        if existing and existing.id != entity.id:
            raise spec.already_exists_error(
                f"{spec.label_indefinite} named {cmd.name!r} already exists."
            )

    changelog_entry = diff_command(entity, cmd)

    entity.name = cmd.name
    entity.label_color = cmd.label_color
    entity.label_font_color = cmd.label_font_color
    entity.description = cmd.description
    entity.changed = now_utc()
    entity.changes = append_changelog(entity.changes, actor.full_name, changelog_entry)

    saved = await repo.save(entity)
    log.info(f"Updated {spec.label} {saved.name!r}, ID={saved.id}.")
    return saved


async def archive_named_entity(
    spec: NamedEntitySpec[TEntity],
    repo: _NamedEntityRepo[TEntity, TFilter],
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
    log.info(f"Archived {spec.label} {saved.name!r}, ID={saved.id}.")
    return saved


async def restore_named_entity(
    spec: NamedEntitySpec[TEntity],
    repo: _NamedEntityRepo[TEntity, TFilter],
    actor: User,
    entity_id: int,
) -> TEntity:
    """Idempotent, same as archive_labeled_entity. Restoring a row whose
    `name` is now held by another live row raises `already_exists_error`
    (409) rather than violating the live-row uniqueness index."""
    spec.rules.assert_can_restore(actor)

    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")

    if entity.archived:
        conflict = await repo.get_by_name(entity.name)
        if conflict and conflict.id != entity.id:
            raise spec.already_exists_error(
                f"{spec.label_indefinite} named {entity.name!r} already exists."
            )

    entity.archived = False
    entity.changed = now_utc()
    entity.changes = append_changelog(
        entity.changes, actor.full_name, f"{spec.label.capitalize()} restored."
    )

    saved = await repo.save(entity)
    log.info(f"Restored {spec.label} {saved.name!r}, ID={saved.id}.")
    return saved


async def get_named_entity(
    spec: NamedEntitySpec[TEntity],
    repo: _NamedEntityRepo[TEntity, TFilter],
    entity_id: int,
) -> TEntity:
    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise spec.not_found_error(f"{spec.label.capitalize()} #{entity_id} not found.")
    return entity


async def get_named_entities(
    repo: _NamedEntityRepo[TEntity, TFilter],
    filters: TFilter,
) -> tuple[int, list[TEntity]]:
    return await repo.get_multi(filters)
