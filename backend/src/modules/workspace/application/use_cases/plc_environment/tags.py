"""
Lists a product's PLC tags, built from its live devices for the product's
PLC environment, or the default one (see plc_naming.py), followed by its
manual tags, and changes them. Reading needs an active user, like reading
the devices; changing needs the rights to edit the product's devices.

A tag built from a device signal is renamed by giving the signal a tag name
of its own, so the list never holds a copy that could drift from the
devices; taking the name off brings the built one back. A manual tag
belongs to no device and keeps its name as written.
"""

from dataclasses import replace

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.plc_environment_dto import ExportColumnDto
from src.modules.workspace.application.dto.plc_tag_dto import PlcTagEnvironmentResult
from src.modules.workspace.application.dto.plc_tag_dto import PlcTagListResult
from src.modules.workspace.application.dto.plc_tag_dto import PlcTagResult
from src.modules.workspace.application.dto.plc_tag_dto import SaveManualPlcTagCommand
from src.modules.workspace.application.dto.plc_tag_dto import SetSignalTagNameCommand
from src.modules.workspace.application.services.plc_environments import environment_of
from src.modules.workspace.domain.entities.plc_manual_tag import PlcManualTag
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.errors import PlcManualTagNotFoundError
from src.modules.workspace.domain.errors import PlcSignalNotFoundError
from src.modules.workspace.domain.errors import PlcTagInvalidError
from src.modules.workspace.domain.errors import ProductDeviceNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.policies.product_device_rules import ProductDeviceRules
from src.modules.workspace.domain.policies.product_device_rules import clean_address
from src.modules.workspace.domain.services.plc_naming import MANUAL_COMMENT_MAX_LENGTH
from src.modules.workspace.domain.services.plc_naming import build_tags
from src.modules.workspace.domain.services.plc_naming import clean_tag_name
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.plc_manual_tag_repository import (
    IPlcManualTagRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class GetProductPlcTags:
    def __init__(
        self,
        product_repo: IProductRepository,
        device_repo: IProductDeviceRepository,
        kind_repo: IProductDeviceKindRepository,
        environment_repo: IPlcEnvironmentRepository,
        manual_repo: IPlcManualTagRepository,
        settings_repo: ICatalogueSettingsRepository,
    ) -> None:
        self._products = product_repo
        self._devices = device_repo
        self._kinds = kind_repo
        self._environments = environment_repo
        self._manual = manual_repo
        self._settings = settings_repo

    async def execute(self, product_id: int) -> PlcTagListResult:
        product = found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        environment = await environment_of(self._environments, product)
        if environment is None:
            return PlcTagListResult(environment=None, tags=[])
        devices = await self._devices.get_by_product(product_id, include_archived=False)
        kinds = {kind.id: kind for kind in await self._kinds.get_many(include_archived=True)}
        by_id = {device.id: device for device in devices}
        manual = await self._manual.get_by_product(product_id)
        # A comment names a signal without a meaning of its own by its kind
        # signal or position, in the instance's language like the export.
        language = (await self._settings.get_general()).default_language
        tags = build_tags(devices, kinds, environment, manual, language)
        return PlcTagListResult(
            environment=PlcTagEnvironmentResult(
                id=environment.id,
                name=environment.name,
                max_tag_length=environment.max_tag_length,
                export_sheet=environment.export_sheet,
                export_columns=[
                    ExportColumnDto(header=c.header, source=c.source, value=c.value)
                    for c in environment.export_columns
                ],
            ),
            tags=[
                PlcTagResult(
                    device_id=tag.device_id,
                    device_name=by_id[tag.device_id].name_utf8 if tag.device_id else "",
                    device_name_ascii=by_id[tag.device_id].name_ascii if tag.device_id else "",
                    component_id=tag.component_id,
                    signal_index=tag.signal_index,
                    name=tag.name,
                    tag_table=tag.tag_table,
                    address=tag.address,
                    comment=tag.comment,
                    signal_type=tag.signal_type,
                    safety=tag.safety,
                    data_type="",
                    overridden=tag.overridden,
                    too_long=tag.too_long,
                    duplicate=tag.duplicate,
                    manual_id=tag.manual_id,
                )
                for tag in tags
            ],
        )


class _ProductWriter:
    def __init__(self, product_repo: IProductRepository, *, uow: IUnitOfWork) -> None:
        self._products = product_repo
        self._uow = uow

    async def _editable_product(self, actor: User, product_id: int) -> Product:
        product = found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        ProductDeviceRules.assert_can_edit(actor, product)
        return product


def _apply_manual(tag: PlcManualTag, cmd: SaveManualPlcTagCommand) -> None:
    comment = " ".join(cmd.comment.split())
    if len(comment) > MANUAL_COMMENT_MAX_LENGTH:
        raise PlcTagInvalidError(
            f"A tag comment is longer than {MANUAL_COMMENT_MAX_LENGTH} characters."
        )
    if cmd.safety and cmd.signal_type == ProductDeviceSignalType.BUS:
        raise PlcTagInvalidError("A bus signal cannot be a safety signal.")
    tag.name = clean_tag_name(cmd.name)
    tag.signal_type = cmd.signal_type
    tag.safety = cmd.safety
    tag.address = clean_address(cmd.address)
    tag.comment = comment


class CreateManualPlcTag(_ProductWriter):
    def __init__(
        self,
        product_repo: IProductRepository,
        manual_repo: IPlcManualTagRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(product_repo, uow=uow)
        self._manual = manual_repo

    async def execute(self, actor: User, product_id: int, cmd: SaveManualPlcTagCommand) -> int:
        await self._editable_product(actor, product_id)
        now = now_utc()
        tag = PlcManualTag(
            id=0,
            created=now,
            changed=now,
            product_id=product_id,
            name="",
            signal_type=cmd.signal_type,
            safety=False,
            address=None,
            comment="",
            sort_order=await self._manual.next_sort_order(product_id),
            creator_id=actor.id,
        )
        _apply_manual(tag, cmd)
        saved = await self._manual.save(tag)
        await self._uow.commit()
        log.info(f"Created manual PLC tag ID={saved.id} of product #{product_id}.")
        return saved.id


class _ManualTagWriter(_ProductWriter):
    def __init__(
        self,
        product_repo: IProductRepository,
        manual_repo: IPlcManualTagRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(product_repo, uow=uow)
        self._manual = manual_repo

    async def _load(self, actor: User, tag_id: int) -> PlcManualTag:
        tag = found_or_raise(
            await self._manual.get_by_id(tag_id),
            PlcManualTagNotFoundError,
            f"Manual PLC tag #{tag_id} not found.",
        )
        await self._editable_product(actor, tag.product_id)
        return tag


class UpdateManualPlcTag(_ManualTagWriter):
    async def execute(self, actor: User, tag_id: int, cmd: SaveManualPlcTagCommand) -> None:
        tag = await self._load(actor, tag_id)
        _apply_manual(tag, cmd)
        tag.changed = now_utc()
        await self._manual.save(tag)
        await self._uow.commit()
        log.info(f"Updated manual PLC tag ID={tag_id}.")


class DeleteManualPlcTag(_ManualTagWriter):
    async def execute(self, actor: User, tag_id: int) -> None:
        tag = await self._load(actor, tag_id)
        await self._manual.delete(tag)
        await self._uow.commit()
        log.info(f"Deleted manual PLC tag ID={tag_id}.")


class SetSignalTagName(_ProductWriter):
    """Gives a device signal a tag name of its own, or takes it off."""

    def __init__(
        self,
        product_repo: IProductRepository,
        device_repo: IProductDeviceRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(product_repo, uow=uow)
        self._devices = device_repo

    async def execute(self, actor: User, device_id: int, cmd: SetSignalTagNameCommand) -> None:
        device = found_or_raise(
            await self._devices.get_by_id(device_id),
            ProductDeviceNotFoundError,
            f"Product device #{device_id} not found.",
        )
        await self._editable_product(actor, device.product_id)
        component = next((c for c in device.components if c.id == cmd.component_id), None)
        if component is None or not 0 <= cmd.signal_index < len(component.signals):
            raise PlcSignalNotFoundError(
                f"Device #{device_id} has no signal {cmd.signal_index} on component "
                f"#{cmd.component_id}."
            )
        name = clean_tag_name(cmd.tag_name) if cmd.tag_name and cmd.tag_name.strip() else None
        signals = list(component.signals)
        signals[cmd.signal_index] = replace(signals[cmd.signal_index], tag_name=name)
        component.signals = signals
        device.changed = now_utc()
        device.changes = append_changelog(
            device.changes,
            actor.full_name,
            f"PLC tag of a signal set to {name}." if name else "PLC tag of a signal reset.",
        )
        await self._devices.save(device)
        await self._uow.commit()
        log.info(f"Set the PLC tag of a signal of device ID={device_id}.")
