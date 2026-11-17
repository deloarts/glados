"""The plans outside Glados a device has to be drawn in, as the device
completeness matrix tracks them. Which of them a machine needs follows its
disciplines; the CAD assembly is always needed."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class DevicePlan(StrValueEnum):
    CAD_ASSEMBLY = "cad_assembly"
    EPLAN = "eplan"
    PNEUMATICS = "pneumatics"
    HYDRAULICS = "hydraulics"
    ROBOT_PROGRAM = "robot_program"


def required_plans(
    *, electrics: bool, pneumatics: bool, hydraulics: bool, robotics: bool
) -> list[DevicePlan]:
    """The plans every device of a machine with these disciplines has to be
    drawn in, in the order the completeness matrix shows them."""
    return [
        DevicePlan.CAD_ASSEMBLY,
        *([DevicePlan.EPLAN] if electrics else []),
        *([DevicePlan.PNEUMATICS] if pneumatics else []),
        *([DevicePlan.HYDRAULICS] if hydraulics else []),
        *([DevicePlan.ROBOT_PROGRAM] if robotics else []),
    ]
