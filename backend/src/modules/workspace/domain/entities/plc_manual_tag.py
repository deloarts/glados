"""
A PLC tag of a machine that belongs to no device, such as a communication
bit, an HMI tag, an internal flag or a spare channel. It is kept on the
product and listed and exported with the tags built from the devices.
Its name is taken as written, so it gets no prefix.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PlcManualTag(Entity):
    created: datetime
    changed: datetime
    product_id: int
    name: str
    signal_type: ProductDeviceSignalType
    safety: bool
    address: str | None
    comment: str
    sort_order: int
    creator_id: int
    changed_by_id: int | None = None
