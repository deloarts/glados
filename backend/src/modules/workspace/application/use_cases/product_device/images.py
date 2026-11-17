"""
Sets and removes the images of a product device: its CAD rendering and the
rendering of the parent assembly it is installed in. Each slot holds one
image: an upload replaces the previous one, whose file is deleted once the
device points at the new one. The files are product files of their own
categories, named after the device's public id so they can be told apart
among the product's files. Images are stored as PNG.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceResult
from src.modules.workspace.application.mappers.product_device_mapper import ProductDeviceMapper
from src.modules.workspace.application.use_cases.product.delete_product_file import (
    DeleteProductFile,
)
from src.modules.workspace.application.use_cases.product.upload_product_file import (
    UploadProductFile,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.errors import ProductDeviceNotFoundError
from src.modules.workspace.domain.errors import ProductFileNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.policies.product_device_rules import ProductDeviceRules
from src.modules.workspace.domain.value_objects.product_device_image_slot import (
    ProductDeviceImageSlot,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

_LABELS = {
    ProductDeviceImageSlot.RENDERING: "Rendering",
    ProductDeviceImageSlot.ASSEMBLY: "Assembly rendering",
}


def _file_id(device: ProductDevice, slot: ProductDeviceImageSlot) -> int | None:
    if slot is ProductDeviceImageSlot.ASSEMBLY:
        return device.assembly_file_id
    return device.rendering_file_id


def _set_file_id(device: ProductDevice, slot: ProductDeviceImageSlot, file_id: int | None) -> None:
    if slot is ProductDeviceImageSlot.ASSEMBLY:
        device.assembly_file_id = file_id
    else:
        device.rendering_file_id = file_id


class _ImageWriter:
    def __init__(
        self,
        device_repo: IProductDeviceRepository,
        product_repo: IProductRepository,
        delete_file: DeleteProductFile,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._devices = device_repo
        self._products = product_repo
        self._delete_file = delete_file
        self._uow = uow

    async def _editable(self, actor: User, device_id: int) -> tuple[ProductDevice, Product]:
        device = found_or_raise(
            await self._devices.get_by_id(device_id),
            ProductDeviceNotFoundError,
            f"Product device #{device_id} not found.",
        )
        product = found_or_raise(
            await self._products.get_by_id(device.product_id),
            ProductNotFoundError,
            f"Product #{device.product_id} not found.",
        )
        ProductDeviceRules.assert_can_edit(actor, product)
        return device, product

    async def _point_to(
        self,
        actor: User,
        device: ProductDevice,
        slot: ProductDeviceImageSlot,
        file_id: int | None,
        entry: str,
    ) -> ProductDevice:
        """Points the slot at `file_id`, commits, and only then deletes the
        file it pointed at before, so a failure never leaves the device
        without the image it had."""
        previous = _file_id(device, slot)
        _set_file_id(device, slot, file_id)
        device.changed = now_utc()
        device.changes = append_changelog(device.changes, actor.full_name, entry)
        saved = await self._devices.save(device)
        await self._uow.commit()
        if previous is not None and previous != file_id:
            try:
                await self._delete_file.execute(actor, previous)
            except ProductFileNotFoundError:
                log.info("Previous device image file #%s was already gone.", previous)
        return saved


class SetProductDeviceImage(_ImageWriter):
    def __init__(
        self,
        device_repo: IProductDeviceRepository,
        product_repo: IProductRepository,
        upload_file: UploadProductFile,
        delete_file: DeleteProductFile,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(device_repo, product_repo, delete_file, uow=uow)
        self._upload_file = upload_file

    async def execute(
        self,
        actor: User,
        device_id: int,
        slot: ProductDeviceImageSlot,
        data: bytes,
        content_type: str,
    ) -> ProductDeviceResult:
        device, product = await self._editable(actor, device_id)
        uploaded = await self._upload_file.execute(
            actor,
            product.id,
            data,
            slot.file_name(str(device.public_id)),
            content_type,
            slot.file_category,
        )
        verb = "replaced" if _file_id(device, slot) is not None else "added"
        saved = await self._point_to(actor, device, slot, uploaded.id, f"{_LABELS[slot]} {verb}.")
        log.info(f"{_LABELS[slot]} of device {saved.name_utf8!r} (ID={saved.id}) set.")
        return ProductDeviceMapper.to_result(saved)


class RemoveProductDeviceImage(_ImageWriter):
    async def execute(
        self, actor: User, device_id: int, slot: ProductDeviceImageSlot
    ) -> ProductDeviceResult:
        device, _ = await self._editable(actor, device_id)
        if _file_id(device, slot) is None:
            return ProductDeviceMapper.to_result(device)
        saved = await self._point_to(actor, device, slot, None, f"{_LABELS[slot]} removed.")
        log.info(f"{_LABELS[slot]} of device {saved.name_utf8!r} (ID={saved.id}) removed.")
        return ProductDeviceMapper.to_result(saved)
