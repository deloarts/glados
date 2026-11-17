"""The two images a product device carries: its own CAD rendering, and a
rendering of the parent assembly it is installed in. Each slot holds one
image; an upload replaces the one before it."""

from enum import unique

from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ProductDeviceImageSlot(StrValueEnum):
    RENDERING = "rendering"
    ASSEMBLY = "assembly"

    @property
    def file_category(self) -> ProductFileCategory:
        if self is ProductDeviceImageSlot.ASSEMBLY:
            return ProductFileCategory.DEVICE_ASSEMBLY
        return ProductFileCategory.DEVICE_RENDERING

    def file_name(self, device_public_id: str) -> str:
        """The stored file's name: the device's public id, with a suffix for
        the assembly so both images of a device can be told apart."""
        suffix = "" if self is ProductDeviceImageSlot.RENDERING else f"-{self.value}"
        return f"{device_public_id}{suffix}.png"
