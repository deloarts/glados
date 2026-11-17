"""A PLC signal of a product device component: its type and what it means,
for example a digital output "extend" on a valve or a digital input
"retracted" on a sensor. An input may name the position of the device's
kind it confirms, so a sensor with two outputs, or a cylinder with
integrated sensing, confirms one position per signal; an output may name
the position it drives to. A signal without a position may instead pick
one of its kind's signals, such as a fault input. Its meaning is free text,
needed only when it names neither. Its PLC tag is built from the device
name and that position's state or command name, or the kind signal's PLC
name, unless the signal brings a suffix or a whole tag name of its own. A
safety signal takes the safety prefix of its type. The PLC address is
entered by hand until the electrical plan can be imported."""

from dataclasses import dataclass
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ProductDeviceSignalType(StrValueEnum):
    DI = "di"
    DO = "do"
    AI = "ai"
    AO = "ao"
    BUS = "bus"


# The signal types that report something to the PLC and so can confirm a
# position.
INPUT_SIGNAL_TYPES = frozenset({ProductDeviceSignalType.DI, ProductDeviceSignalType.AI})
# The signal types the PLC sets and so can drive a position.
OUTPUT_SIGNAL_TYPES = frozenset({ProductDeviceSignalType.DO, ProductDeviceSignalType.AO})


@dataclass(frozen=True)
class ProductDeviceSignal:
    signal_type: ProductDeviceSignalType
    meaning: str
    confirms_position_id: int | None = None
    drives_position_id: int | None = None
    safety: bool = False
    address: str | None = None
    tag_suffix: str | None = None
    tag_name: str | None = None
    kind_signal_id: int | None = None
