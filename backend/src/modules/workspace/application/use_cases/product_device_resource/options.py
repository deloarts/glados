"""
Lists, creates, edits, moves, places, archives and restores the plain option lists
of product devices: driving media, component roles and energy behaviours.
Labels need a text in the instance's default language. A driving medium's
letter goes into device names, so it is unique across all media and frozen
once a device uses it.
"""

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.localized_text import require_language
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_device_resource_dto import (
    CreateProductDeviceOptionCommand,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceOptionResult,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    UpdateProductDeviceOptionCommand,
)
from src.modules.workspace.application.mappers.product_device_resource_mapper import (
    ProductDeviceResourceMapper,
)
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.errors import ProductDeviceLetterFrozenError
from src.modules.workspace.domain.errors import ProductDeviceLetterTakenError
from src.modules.workspace.domain.errors import ProductDeviceOptionNotFoundError
from src.modules.workspace.domain.services.product_device_resource_rules import (
    ProductDeviceResourceRules,
)
from src.modules.workspace.domain.services.product_device_resource_rules import normalize_letter
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceOptionRepository,
)
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.list_order import changed_sort_orders
from src.shared_kernel.domain.services.list_order import move_entry
from src.shared_kernel.domain.services.list_order import place_entry
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


async def _label(settings: ICatalogueSettingsRepository, raw: dict[str, str]) -> LocalizedText:
    label = LocalizedText.of(raw)
    require_language(label, (await settings.get_general()).default_language, "label")
    return label


async def _assert_letter_free(
    options: IProductDeviceOptionRepository, letter: str | None, own_id: int
) -> None:
    if letter is None:
        return
    holder = await options.get_by_letter(letter)
    if holder is not None and holder.id != own_id:
        raise ProductDeviceLetterTakenError(
            f"The letter {letter!r} is already used by another driving medium."
        )


class GetProductDeviceOptions:
    def __init__(self, option_repo: IProductDeviceOptionRepository) -> None:
        self._options = option_repo

    async def execute(
        self, category: ProductDeviceOptionCategory | None, include_archived: bool
    ) -> list[ProductDeviceOptionResult]:
        options = await self._options.get_many(category, include_archived)
        return [ProductDeviceResourceMapper.option_to_result(o) for o in options]


class CreateProductDeviceOption:
    def __init__(
        self,
        option_repo: IProductDeviceOptionRepository,
        settings_repo: ICatalogueSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._options = option_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: CreateProductDeviceOptionCommand
    ) -> ProductDeviceOptionResult:
        ProductDeviceResourceRules.assert_can_write(actor)
        label = await _label(self._settings, cmd.label)
        letter = normalize_letter(cmd.category, cmd.letter)
        await _assert_letter_free(self._options, letter, own_id=0)

        now = now_utc()
        saved = await self._options.save(
            ProductDeviceOption(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog([], actor.full_name, "Entry created."),
                category=cmd.category,
                label=label,
                letter=letter,
                sort_order=await self._options.next_sort_order(cmd.category),
                creator_id=actor.id,
                creator=actor,
            )
        )
        await self._uow.commit()
        log.info(f"Created product device option ID={saved.id} ({saved.category.value}).")
        return ProductDeviceResourceMapper.option_to_result(saved)


class UpdateProductDeviceOption:
    def __init__(
        self,
        option_repo: IProductDeviceOptionRepository,
        device_repo: IProductDeviceRepository,
        settings_repo: ICatalogueSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._options = option_repo
        self._devices = device_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, option_id: int, cmd: UpdateProductDeviceOptionCommand
    ) -> ProductDeviceOptionResult:
        ProductDeviceResourceRules.assert_can_write(actor)
        option = found_or_raise(
            await self._options.get_by_id(option_id),
            ProductDeviceOptionNotFoundError,
            f"Product device option #{option_id} not found.",
        )
        label = await _label(self._settings, cmd.label)
        letter = normalize_letter(option.category, cmd.letter)
        if letter != option.letter:
            if await self._devices.count_by_driving_medium(option.id):
                raise ProductDeviceLetterFrozenError(
                    f"The letter {option.letter!r} is part of existing device names and "
                    "cannot change."
                )
            await _assert_letter_free(self._options, letter, own_id=option.id)

        option.label = label
        option.letter = letter
        if cmd.sort_order is not None:
            option.sort_order = cmd.sort_order
        option.changed = now_utc()
        option.changes = append_changelog(option.changes, actor.full_name, "Entry updated.")
        saved = await self._options.save(option)
        await self._uow.commit()
        log.info(f"Updated product device option ID={saved.id}.")
        return ProductDeviceResourceMapper.option_to_result(saved)


class SetProductDeviceOptionArchived:
    def __init__(self, option_repo: IProductDeviceOptionRepository, *, uow: IUnitOfWork) -> None:
        self._options = option_repo
        self._uow = uow

    async def execute(
        self, actor: User, option_id: int, archived: bool
    ) -> ProductDeviceOptionResult:
        ProductDeviceResourceRules.assert_can_archive(actor)
        option = found_or_raise(
            await self._options.get_by_id(option_id),
            ProductDeviceOptionNotFoundError,
            f"Product device option #{option_id} not found.",
        )
        option.archived = archived
        option.changed = now_utc()
        option.changes = append_changelog(
            option.changes, actor.full_name, "Entry archived." if archived else "Entry restored."
        )
        saved = await self._options.save(option)
        await self._uow.commit()
        log.info(f"{'Archived' if archived else 'Restored'} product device option ID={saved.id}.")
        return ProductDeviceResourceMapper.option_to_result(saved)


class MoveProductDeviceOption:
    """Moves an entry one place up or down within its category, so the
    entries used most can lead the pickers. Returns the whole category, archived
    entries included, in its new order."""

    def __init__(self, option_repo: IProductDeviceOptionRepository, *, uow: IUnitOfWork) -> None:
        self._options = option_repo
        self._uow = uow

    async def execute(
        self, actor: User, option_id: int, direction: ListMoveDirection
    ) -> list[ProductDeviceOptionResult]:
        ProductDeviceResourceRules.assert_can_write(actor)
        option = found_or_raise(
            await self._options.get_by_id(option_id),
            ProductDeviceOptionNotFoundError,
            f"Product device option #{option_id} not found.",
        )
        entries = await self._options.get_many(option.category, include_archived=True)
        before = {entry.id: entry.sort_order for entry in entries}
        ordered = move_entry(entries, option.id, direction)
        await self._options.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(f"Moved product device option ID={option.id} {direction.value}.")
        return [ProductDeviceResourceMapper.option_to_result(e) for e in ordered]


class PlaceProductDeviceOption:
    """Puts an entry directly after `after_id`, or before `before_id`, within
    its category, which is what dragging its row does. Both neighbours must
    be of the same category. Returns the whole category, archived entries
    included, in its new order."""

    def __init__(self, option_repo: IProductDeviceOptionRepository, *, uow: IUnitOfWork) -> None:
        self._options = option_repo
        self._uow = uow

    async def execute(
        self, actor: User, option_id: int, *, after_id: int | None, before_id: int | None
    ) -> list[ProductDeviceOptionResult]:
        ProductDeviceResourceRules.assert_can_write(actor)
        option = found_or_raise(
            await self._options.get_by_id(option_id),
            ProductDeviceOptionNotFoundError,
            f"Product device option #{option_id} not found.",
        )
        entries = await self._options.get_many(option.category, include_archived=True)
        known = {entry.id for entry in entries}
        for neighbour in (after_id, before_id):
            if neighbour is not None and neighbour not in known:
                raise ProductDeviceOptionNotFoundError(
                    f"Product device option #{neighbour} not found in this list."
                )
        before = {entry.id: entry.sort_order for entry in entries}
        ordered = place_entry(entries, option.id, after_id=after_id, before_id=before_id)
        await self._options.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(
            f"Placed product device option ID={option.id} after {after_id} / before {before_id}."
        )
        return [ProductDeviceResourceMapper.option_to_result(e) for e in ordered]
