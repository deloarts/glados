"""
An entry of one of the plain lists product devices pick from: a driving
medium (with the letter that goes into the device name), a component role
or an energy behaviour. The lists are maintained by hand in the resources
section and start empty. An entry in use is archived, never deleted, so
existing devices keep resolving it.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductDeviceOption(Entity):
    created: datetime
    changed: datetime
    changes: list[str]

    category: ProductDeviceOptionCategory
    label: LocalizedText
    # Driving media only; None for every other category.
    letter: str | None
    sort_order: int

    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    archived: bool = False
