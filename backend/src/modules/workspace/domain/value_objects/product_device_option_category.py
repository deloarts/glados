"""The hand-maintained lists a product device or flow sequence picks from
that are a plain label each. Driving media also carry the letter that goes
into the device name; the other categories have none."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ProductDeviceOptionCategory(StrValueEnum):
    DRIVING_MEDIUM = "driving_medium"
    COMPONENT_ROLE = "component_role"
    # What a device does when its energy is lost or comes back; one list
    # serves both questions.
    ENERGY_BEHAVIOUR = "energy_behaviour"
    # Names proposed for a product's flow sequences (automatic, homing, ...);
    # a sequence's name is free text, these only fill it in.
    SEQUENCE_NAME = "sequence_name"
