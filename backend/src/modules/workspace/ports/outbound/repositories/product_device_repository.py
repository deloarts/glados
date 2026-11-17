"""
Persistence port for product devices and their components.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent


@runtime_checkable
class IProductDeviceRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductDevice | None:
        """With its components, archived or not."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_by_product(self, product_id: int, include_archived: bool) -> list[ProductDevice]:
        """With their components, ordered by UTF-8 name."""
        ...

    async def get_by_name(self, product_id: int, name_utf8: str) -> ProductDevice | None:
        """Archived devices included, since their names stay taken."""
        ...

    async def get_by_ascii_key(self, product_id: int, name_ascii_key: str) -> ProductDevice | None:
        """Archived devices included."""
        ...

    async def max_number(self, product_id: int, group_key: str) -> int | None:
        """The highest number in use for this location, name and letter,
        archived devices included."""
        ...

    async def count_by_product(self, product_id: int) -> int:
        """Archived devices included."""
        ...

    async def count_by_driving_medium(self, option_id: int) -> int:
        """Archived devices included."""
        ...

    async def count_driven_by(self, device_id: int) -> int:
        """The devices this device drives, archived ones included."""
        ...

    async def get_component_by_eplan_tag(
        self, product_id: int, eplan_tag: str
    ) -> ProductDeviceComponent | None: ...

    async def save(self, device: ProductDevice) -> ProductDevice:
        """Insert (id == 0) or update (id > 0) the device together with its
        components: components with id 0 are inserted, the others updated,
        and stored components missing from the list are deleted."""
        ...
