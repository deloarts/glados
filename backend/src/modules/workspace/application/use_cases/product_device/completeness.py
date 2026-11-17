"""
The completeness of a product's devices: for each device the plans outside
Glados it is ticked as drawn in, with who ticked it and when, and whether a
flow sequence moves or checks it. A device counts as in a sequence when a
valid released revision refers to it ("released") or else a draft does
("draft"); a driven device counts through its driver. Reading needs an
active user; ticking needs the rights to edit the product's devices.
"""

from dataclasses import dataclass
from typing import Literal

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.entities.product_device_check import ProductDeviceCheck
from src.modules.workspace.domain.errors import ProductDeviceNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.policies.product_device_rules import ProductDeviceRules
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.modules.workspace.ports.outbound.product_documents_port import IProductDocuments
from src.modules.workspace.ports.outbound.repositories.product_device_check_repository import (
    IProductDeviceCheckRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.shared_kernel.domain.services.clock import now_utc

SequenceCoverage = Literal["released", "draft", "none"]


@dataclass(frozen=True)
class DeviceCompleteness:
    device_id: int
    checks: list[ProductDeviceCheck]
    sequence_coverage: SequenceCoverage


class GetProductDeviceCompleteness:
    def __init__(
        self,
        product_repo: IProductRepository,
        device_repo: IProductDeviceRepository,
        check_repo: IProductDeviceCheckRepository,
        documents: IProductDocuments,
    ) -> None:
        self._products = product_repo
        self._devices = device_repo
        self._checks = check_repo
        self._documents = documents

    async def execute(self, product_id: int) -> list[DeviceCompleteness]:
        found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        devices = await self._devices.get_by_product(product_id, include_archived=False)
        checks = await self._checks.get_by_product(product_id)
        sequenced = await self._documents.sequenced_devices(product_id)
        released, drafts = sequenced.released, sequenced.drafts

        def coverage(device_id: int, driven_by_id: int | None) -> SequenceCoverage:
            ids = {device_id} | ({driven_by_id} if driven_by_id else set())
            if ids & released:
                return "released"
            return "draft" if ids & drafts else "none"

        return [
            DeviceCompleteness(
                device_id=device.id,
                checks=[c for c in checks if c.device_id == device.id],
                sequence_coverage=coverage(device.id, device.driven_by_id),
            )
            for device in devices
        ]


class SetProductDeviceCheck:
    def __init__(
        self,
        product_repo: IProductRepository,
        device_repo: IProductDeviceRepository,
        check_repo: IProductDeviceCheckRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._products = product_repo
        self._devices = device_repo
        self._checks = check_repo
        self._uow = uow

    async def execute(self, actor: User, device_id: int, plan: DevicePlan, checked: bool) -> None:
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
        current = await self._checks.get(device_id, plan)
        if checked and current is None:
            await self._checks.add(
                ProductDeviceCheck(
                    id=0,
                    device_id=device_id,
                    plan=plan,
                    checked_by_id=actor.id,
                    checked_at=now_utc(),
                )
            )
        elif not checked and current is not None:
            await self._checks.remove(device_id, plan)
        await self._uow.commit()
        log.info(f"Device ID={device_id} {plan.value} {'ticked' if checked else 'unticked'}.")
