"""
Lists, creates, edits, moves, archives and restores product device kinds. A kind
is saved together with its positions, parameters and signals; one taken out
of the list is archived, never deleted, so devices keep resolving it (see
product_device_resource_rules.sync_positions).
"""

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.localized_text import require_language
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceKindResult,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    SaveProductDeviceKindCommand,
)
from src.modules.workspace.application.mappers.product_device_resource_mapper import (
    ProductDeviceResourceMapper,
)
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.errors import ProductDeviceKindNotFoundError
from src.modules.workspace.domain.services.product_device_resource_rules import ParameterDraft
from src.modules.workspace.domain.services.product_device_resource_rules import PositionDraft
from src.modules.workspace.domain.services.product_device_resource_rules import (
    ProductDeviceResourceRules,
)
from src.modules.workspace.domain.services.product_device_resource_rules import SignalDraft
from src.modules.workspace.domain.services.product_device_resource_rules import sync_parameters
from src.modules.workspace.domain.services.product_device_resource_rules import sync_positions
from src.modules.workspace.domain.services.product_device_resource_rules import sync_signals
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.list_order import changed_sort_orders
from src.shared_kernel.domain.services.list_order import move_entry
from src.shared_kernel.domain.services.list_order import place_entry
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


def _apply(
    kind: ProductDeviceKind, cmd: SaveProductDeviceKindCommand, default_language: str
) -> None:
    """Writes the command's label and children onto `kind`, every label
    checked for the default language."""
    label = LocalizedText.of(cmd.label)
    require_language(label, default_language, "kind label")
    positions: list[PositionDraft] = []
    for position in cmd.positions:
        position_label = LocalizedText.of(position.label)
        require_language(position_label, default_language, "position label")
        positions.append(
            PositionDraft(
                position.id,
                position_label,
                position.takes_value,
                position.unit,
                position.plc_state_name,
                position.plc_command_name,
            )
        )
    parameters: list[ParameterDraft] = []
    for parameter in cmd.parameters:
        parameter_label = LocalizedText.of(parameter.label)
        require_language(parameter_label, default_language, "parameter label")
        parameters.append(
            ParameterDraft(parameter.id, parameter_label, parameter.unit, parameter.value_type)
        )
    signals: list[SignalDraft] = []
    for signal in cmd.signals:
        signal_label = LocalizedText.of(signal.label)
        require_language(signal_label, default_language, "signal label")
        signals.append(SignalDraft(signal.id, signal_label, signal.signal_type, signal.plc_name))

    kind.label = label
    kind.without_driving_medium = cmd.without_driving_medium
    if cmd.sort_order is not None:
        kind.sort_order = cmd.sort_order
    kind.positions = sync_positions(kind.id, kind.positions, positions)
    kind.parameters = sync_parameters(kind.id, kind.parameters, parameters)
    kind.signals = sync_signals(kind.id, kind.signals, signals)


class GetProductDeviceKinds:
    def __init__(self, kind_repo: IProductDeviceKindRepository) -> None:
        self._kinds = kind_repo

    async def execute(self, include_archived: bool) -> list[ProductDeviceKindResult]:
        kinds = await self._kinds.get_many(include_archived)
        return [ProductDeviceResourceMapper.kind_to_result(k) for k in kinds]


class CreateProductDeviceKind:
    def __init__(
        self,
        kind_repo: IProductDeviceKindRepository,
        settings_repo: ICatalogueSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._kinds = kind_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: SaveProductDeviceKindCommand
    ) -> ProductDeviceKindResult:
        ProductDeviceResourceRules.assert_can_write(actor)
        now = now_utc()
        kind = ProductDeviceKind(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Kind created."),
            label=LocalizedText(),
            sort_order=await self._kinds.next_sort_order(),
            creator_id=actor.id,
            creator=actor,
        )
        _apply(kind, cmd, (await self._settings.get_general()).default_language)
        saved = await self._kinds.save(kind)
        await self._uow.commit()
        log.info(f"Created product device kind ID={saved.id}.")
        return ProductDeviceResourceMapper.kind_to_result(saved)


class UpdateProductDeviceKind:
    def __init__(
        self,
        kind_repo: IProductDeviceKindRepository,
        settings_repo: ICatalogueSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._kinds = kind_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, kind_id: int, cmd: SaveProductDeviceKindCommand
    ) -> ProductDeviceKindResult:
        ProductDeviceResourceRules.assert_can_write(actor)
        kind = found_or_raise(
            await self._kinds.get_by_id(kind_id),
            ProductDeviceKindNotFoundError,
            f"Product device kind #{kind_id} not found.",
        )
        _apply(kind, cmd, (await self._settings.get_general()).default_language)
        kind.changed = now_utc()
        kind.changes = append_changelog(kind.changes, actor.full_name, "Kind updated.")
        saved = await self._kinds.save(kind)
        await self._uow.commit()
        log.info(f"Updated product device kind ID={saved.id}.")
        return ProductDeviceResourceMapper.kind_to_result(saved)


class SetProductDeviceKindArchived:
    def __init__(self, kind_repo: IProductDeviceKindRepository, *, uow: IUnitOfWork) -> None:
        self._kinds = kind_repo
        self._uow = uow

    async def execute(self, actor: User, kind_id: int, archived: bool) -> ProductDeviceKindResult:
        ProductDeviceResourceRules.assert_can_archive(actor)
        kind = found_or_raise(
            await self._kinds.get_by_id(kind_id),
            ProductDeviceKindNotFoundError,
            f"Product device kind #{kind_id} not found.",
        )
        kind.archived = archived
        kind.changed = now_utc()
        kind.changes = append_changelog(
            kind.changes, actor.full_name, "Kind archived." if archived else "Kind restored."
        )
        saved = await self._kinds.save(kind)
        await self._uow.commit()
        log.info(f"{'Archived' if archived else 'Restored'} product device kind ID={saved.id}.")
        return ProductDeviceResourceMapper.kind_to_result(saved)


class MoveProductDeviceKind:
    """Moves a kind one place up or down, so the kinds used most can lead
    the pickers. Returns every kind, archived ones included, in the new
    order."""

    def __init__(self, kind_repo: IProductDeviceKindRepository, *, uow: IUnitOfWork) -> None:
        self._kinds = kind_repo
        self._uow = uow

    async def execute(
        self, actor: User, kind_id: int, direction: ListMoveDirection
    ) -> list[ProductDeviceKindResult]:
        ProductDeviceResourceRules.assert_can_write(actor)
        kind = found_or_raise(
            await self._kinds.get_by_id(kind_id),
            ProductDeviceKindNotFoundError,
            f"Product device kind #{kind_id} not found.",
        )
        kinds = await self._kinds.get_many(include_archived=True)
        before = {k.id: k.sort_order for k in kinds}
        ordered = move_entry(kinds, kind.id, direction)
        await self._kinds.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(f"Moved product device kind ID={kind.id} {direction.value}.")
        return [ProductDeviceResourceMapper.kind_to_result(k) for k in ordered]


class PlaceProductDeviceKind:
    """Puts a kind directly after `after_id`, or before `before_id`, which is
    what dragging its row does. Returns every kind, archived ones included,
    in the new order."""

    def __init__(self, kind_repo: IProductDeviceKindRepository, *, uow: IUnitOfWork) -> None:
        self._kinds = kind_repo
        self._uow = uow

    async def execute(
        self, actor: User, kind_id: int, *, after_id: int | None, before_id: int | None
    ) -> list[ProductDeviceKindResult]:
        ProductDeviceResourceRules.assert_can_write(actor)
        kinds = await self._kinds.get_many(include_archived=True)
        known = {k.id for k in kinds}
        for wanted in (kind_id, after_id, before_id):
            if wanted is not None and wanted not in known:
                raise ProductDeviceKindNotFoundError(f"Product device kind #{wanted} not found.")
        before = {k.id: k.sort_order for k in kinds}
        ordered = place_entry(kinds, kind_id, after_id=after_id, before_id=before_id)
        await self._kinds.set_sort_orders(changed_sort_orders(before, ordered))
        await self._uow.commit()
        log.info(f"Placed product device kind ID={kind_id} after {after_id} / before {before_id}.")
        return [ProductDeviceResourceMapper.kind_to_result(k) for k in ordered]
