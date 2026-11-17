"""
Why a machine went down. Used both for the actual reason reported when a
downtime is added and for filtering the downtime list.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class MachineDowntimeReason(StrValueEnum):
    BREAKDOWN = "breakdown"
    MAINTENANCE = "maintenance"
    TOOLING = "tooling"
    NO_OPERATOR = "no_operator"
    NO_MATERIAL = "no_material"
    OTHER = "other"
