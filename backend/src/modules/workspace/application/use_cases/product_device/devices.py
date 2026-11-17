"""
Lists, reads, creates, edits, archives and restores the devices of a
product, and previews a device name while it is being typed. Reading needs
only an active user, like reading the product; changing a device needs the
rights to edit its product (see ProductDeviceRules).
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_device_dto import PreviewProductDeviceNameCommand
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceNamePreviewResult
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceResult
from src.modules.workspace.application.dto.product_device_dto import SaveProductDeviceCommand
from src.modules.workspace.application.mappers.product_device_mapper import ProductDeviceMapper
from src.modules.workspace.application.services.plc_environments import environment_of
from src.modules.workspace.application.use_cases.product_device.assembler import (
    ProductDeviceAssembler,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.errors import ProductDeviceNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.policies.product_device_naming import compose_device_name
from src.modules.workspace.domain.policies.product_device_naming import invalid_characters
from src.modules.workspace.domain.policies.product_device_naming import with_product_number
from src.modules.workspace.domain.policies.product_device_rules import ProductDeviceRules
from src.modules.workspace.domain.services.plc_naming import longest_tag_length
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_check_repository import (
    IProductDeviceCheckRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


async def _product(products: IProductRepository, product_id: int) -> Product:
    return found_or_raise(
        await products.get_by_id(product_id),
        ProductNotFoundError,
        f"Product #{product_id} not found.",
    )


async def _device(devices: IProductDeviceRepository, device_id: int) -> ProductDevice:
    return found_or_raise(
        await devices.get_by_id(device_id),
        ProductDeviceNotFoundError,
        f"Product device #{device_id} not found.",
    )


class GetProductDevices:
    def __init__(
        self, product_repo: IProductRepository, device_repo: IProductDeviceRepository
    ) -> None:
        self._products = product_repo
        self._devices = device_repo

    async def execute(self, product_id: int, include_archived: bool) -> list[ProductDeviceResult]:
        await _product(self._products, product_id)
        devices = await self._devices.get_by_product(product_id, include_archived)
        return [ProductDeviceMapper.to_result(d) for d in devices]


class GetProductDevice:
    def __init__(self, device_repo: IProductDeviceRepository) -> None:
        self._devices = device_repo

    async def execute(self, device_id: int) -> ProductDeviceResult:
        return ProductDeviceMapper.to_result(await _device(self._devices, device_id))


class CreateProductDevice:
    def __init__(
        self,
        product_repo: IProductRepository,
        assembler: ProductDeviceAssembler,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._products = product_repo
        self._assembler = assembler
        self._uow = uow

    async def execute(
        self, actor: User, product_id: int, cmd: SaveProductDeviceCommand
    ) -> ProductDeviceResult:
        product = await _product(self._products, product_id)
        ProductDeviceRules.assert_can_edit(actor, product)

        now = now_utc()
        device = ProductDevice(
            id=0,
            created=now,
            changed=now,
            changes=[],
            product_id=product.id,
            location="",
            name="",
            driving_medium_id=0,
            number=0,
            name_utf8="",
            name_ascii="",
            name_ascii_key="",
            group_key="",
            kind_id=0,
            creator_id=actor.id,
            creator=actor,
        )
        await self._assembler.apply(device, product, cmd)
        device.changes = append_changelog(
            [], actor.full_name, f"Device {device.name_utf8} created."
        )
        saved = await self._assembler.devices.save(device)
        await self._uow.commit()
        log.info(f"Created device {saved.name_utf8!r} (ID={saved.id}) of product #{product.id}.")
        return ProductDeviceMapper.to_result(saved)


class UpdateProductDevice:
    """Saves an edited device. A rename takes the device's plan ticks away,
    because every plan that carries the name has to follow."""

    def __init__(
        self,
        product_repo: IProductRepository,
        assembler: ProductDeviceAssembler,
        *,
        uow: IUnitOfWork,
        check_repo: IProductDeviceCheckRepository | None = None,
    ) -> None:
        self._products = product_repo
        self._assembler = assembler
        self._uow = uow
        self._checks = check_repo

    async def execute(
        self, actor: User, device_id: int, cmd: SaveProductDeviceCommand
    ) -> ProductDeviceResult:
        await self._assembler.devices.lock_for_update(device_id)
        device = await _device(self._assembler.devices, device_id)
        product = await _product(self._products, device.product_id)
        ProductDeviceRules.assert_can_edit(actor, product)
        assert_edit_version(device, cmd.expected_edit_version, what=f"Device #{device.id}")

        previous_name = device.name_utf8
        await self._assembler.apply(device, product, cmd)
        device.changed = now_utc()
        renamed = device.name_utf8 != previous_name
        entry = (
            f"Device renamed from {previous_name} to {device.name_utf8}."
            if renamed
            else "Device updated."
        )
        if renamed and self._checks is not None and await self._checks.remove_all(device.id):
            entry += " Its plan ticks were taken away."
        device.changes = append_changelog(device.changes, actor.full_name, entry)
        saved = await self._assembler.devices.save(device)
        await self._uow.commit()
        log.info(f"Updated device {saved.name_utf8!r} (ID={saved.id}).")
        return ProductDeviceMapper.to_result(saved)


class SetProductDeviceArchived:
    def __init__(
        self,
        product_repo: IProductRepository,
        device_repo: IProductDeviceRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._products = product_repo
        self._devices = device_repo
        self._uow = uow

    async def execute(self, actor: User, device_id: int, archived: bool) -> ProductDeviceResult:
        device = await _device(self._devices, device_id)
        product = await _product(self._products, device.product_id)
        ProductDeviceRules.assert_can_edit(actor, product)

        device.archived = archived
        device.changed = now_utc()
        device.changes = append_changelog(
            device.changes, actor.full_name, "Device archived." if archived else "Device restored."
        )
        saved = await self._devices.save(device)
        await self._uow.commit()
        log.info(f"{'Archived' if archived else 'Restored'} device ID={saved.id}.")
        return ProductDeviceMapper.to_result(saved)


class PreviewProductDeviceName:
    """The name a device would get, for the live preview while typing. An
    invalid character is reported instead of raised, and the number is the
    next free one unless given. With a kind it also tells the longest PLC
    tag the name produces and the limit of the product's PLC environment,
    so the dialog can warn before the name is saved."""

    def __init__(
        self,
        product_repo: IProductRepository,
        assembler: ProductDeviceAssembler,
        environment_repo: IPlcEnvironmentRepository | None = None,
    ) -> None:
        self._products = product_repo
        self._assembler = assembler
        self._environments = environment_repo

    async def execute(
        self, product_id: int, cmd: PreviewProductDeviceNameCommand
    ) -> ProductDeviceNamePreviewResult:
        product = await _product(self._products, product_id)
        current = (
            await self._assembler.devices.get_by_id(cmd.device_id)
            if cmd.device_id is not None
            else None
        )
        if current is not None and current.product_id != product.id:
            current = None

        bad = invalid_characters(cmd.location) + [
            c for c in invalid_characters(cmd.name) if c not in invalid_characters(cmd.location)
        ]
        if bad or not cmd.name.strip():
            return ProductDeviceNamePreviewResult(
                number=cmd.number or 1,
                name_utf8="",
                name_ascii="",
                full_name_utf8="",
                full_name_ascii="",
                invalid_characters=bad,
                taken=False,
            )

        parts = await self._assembler.name_parts(
            cmd.location,
            cmd.name,
            cmd.driving_medium_id,
            current.driving_medium_id if current else None,
        )
        number = await self._assembler.number_for(product.id, parts, cmd.number, current)
        name = compose_device_name(parts.location, parts.name, parts.letter, number)
        full = with_product_number(product.product_number, name)
        return ProductDeviceNamePreviewResult(
            number=number,
            name_utf8=name.utf8,
            name_ascii=name.ascii,
            full_name_utf8=full.utf8,
            full_name_ascii=full.ascii,
            invalid_characters=[],
            taken=await self._assembler.name_taken(product.id, name, current.id if current else 0),
            **await self._tag_length(product, name.utf8, cmd.kind_id),
        )

    async def _tag_length(
        self, product: Product, name_utf8: str, kind_id: int | None
    ) -> dict[str, int | None]:
        environment = await environment_of(self._environments, product)
        kind = await self._assembler.kinds.get_by_id(kind_id) if kind_id else None
        if environment is None or kind is None:
            return {"longest_tag_length": None, "max_tag_length": None}
        return {
            "longest_tag_length": longest_tag_length(name_utf8, kind, environment),
            "max_tag_length": environment.max_tag_length,
        }
