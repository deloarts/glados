"""
Repository interface for the plan ticks of devices.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.product_device_check import ProductDeviceCheck
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan


@runtime_checkable
class IProductDeviceCheckRepository(Protocol):
    async def get_by_product(self, product_id: int) -> list[ProductDeviceCheck]: ...

    async def get(self, device_id: int, plan: DevicePlan) -> ProductDeviceCheck | None: ...

    async def add(self, check: ProductDeviceCheck) -> ProductDeviceCheck: ...

    async def remove(self, device_id: int, plan: DevicePlan) -> None: ...

    async def remove_all(self, device_id: int) -> int:
        """Takes every tick of the device away; returns how many there were."""
        ...
