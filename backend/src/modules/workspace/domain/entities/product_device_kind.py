"""
A kind of product device (linear drive, gripper, electric motor, ...),
maintained by hand in the resources section. A kind defines the positions
its devices can be in and the technical parameters they carry. Positions are
the shared vocabulary of a device's initial position, of the end position a
sensor confirms and of the moves in a later flow list, so an action is
always "move to position X".

A kind also lists the signals its devices typically have besides the
positions, such as the fault and ready signals of a servo axis. A device
signal picks one by id, which gives it its signal type, its meaning in every
language and the PLC name that ends its tag.

Positions, parameters and signals are edited together with their kind. One
that is taken out of the list is archived, never deleted, because devices
may reference it by id.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductDeviceKindPosition(Entity):
    kind_id: int
    label: LocalizedText
    # Whether a device in this position needs a value, such as the stroke
    # of an intermediate position.
    takes_value: bool
    unit: str | None
    sort_order: int
    archived: bool = False
    # The tag suffixes of the position (see plc_naming.py): the state name
    # for an input that confirms it, such as "AUS", and the command name for
    # an output that drives to it, such as "Ausfahren".
    plc_state_name: str | None = None
    plc_command_name: str | None = None


@dataclass
class ProductDeviceKindParameter(Entity):
    kind_id: int
    label: LocalizedText
    unit: str | None
    value_type: ProductDeviceParameterType
    sort_order: int
    archived: bool = False


@dataclass
class ProductDeviceKindSignal(Entity):
    kind_id: int
    label: LocalizedText
    signal_type: ProductDeviceSignalType
    # The tag suffix of a signal that picks it (see plc_naming.py), such as
    # "Stoerung".
    plc_name: str
    sort_order: int
    archived: bool = False


@dataclass
class ProductDeviceKind(Entity):
    created: datetime
    changed: datetime
    changes: list[str]

    label: LocalizedText
    sort_order: int

    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    archived: bool = False
    # Operator devices such as buttons, key switches and indicator lamps:
    # their devices have no driving medium, so their names carry no letter
    # and a number only from the second device of a name on.
    without_driving_medium: bool = False

    # Archived children included; callers filter where they offer choices.
    positions: list[ProductDeviceKindPosition] = field(default_factory=list)
    parameters: list[ProductDeviceKindParameter] = field(default_factory=list)
    signals: list[ProductDeviceKindSignal] = field(default_factory=list)

    def live_positions(self) -> list[ProductDeviceKindPosition]:
        return [p for p in self.positions if not p.archived]

    def live_parameters(self) -> list[ProductDeviceKindParameter]:
        return [p for p in self.parameters if not p.archived]
