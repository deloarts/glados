"""File categories for Product catalogue entries: preview and reference
images, specification documents, and the images of the product's devices.
No geometry categories, since concrete geometry lives on the made items
beneath a product."""

from enum import Enum
from enum import unique


@unique
class ProductFileCategory(str, Enum):
    """A product is a commercial grouping above projects; concrete geometry
    lives on the made items beneath it, so the CAD categories carried by
    bought and made items have no owner at this level. A reference photo and
    specification documents do."""

    THUMBNAIL = "thumbnail"  # singleton, small preview image
    IMAGE = "image"  # singleton, full-size reference photo
    PDF = "pdf"  # multiple, specification / customer drawing
    # Images of the product's devices: one CAD rendering per device, and a
    # top-down overview of the whole product the device markers sit on.
    DEVICE_RENDERING = "device_rendering"  # multiple, referenced by devices
    # The parent assembly a device is installed in, one per device.
    DEVICE_ASSEMBLY = "device_assembly"  # multiple, referenced by devices
    DEVICE_OVERVIEW = "device_overview"  # singleton

    @classmethod
    def singletons(cls) -> set["ProductFileCategory"]:
        return {cls.THUMBNAIL, cls.IMAGE, cls.DEVICE_OVERVIEW}

    @classmethod
    def images(cls) -> frozenset["ProductFileCategory"]:
        return frozenset(
            {
                cls.THUMBNAIL,
                cls.IMAGE,
                cls.DEVICE_RENDERING,
                cls.DEVICE_ASSEMBLY,
                cls.DEVICE_OVERVIEW,
            }
        )

    def is_singleton(self) -> bool:
        return self in self.singletons()
