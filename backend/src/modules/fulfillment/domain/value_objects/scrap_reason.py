"""
Classification for pieces that leave a lot without being delivered,
whether they broke during internal production or were rejected at goods
receipt. Stored as a plain string column (production_order_completion_
table.scrap_reason, order_item_delivery_table.rejection_reason) and
validated at the API boundary by the schema layer, not by a DB enum type,
so a later addition (e.g. a concession/repair outcome) needs no schema
change.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ScrapReason(StrValueEnum):
    """Why a piece was scrapped or rejected."""

    OPERATOR_ERROR = "operator_error"
    TOOL_BREAKAGE = "tool_breakage"
    MACHINE_FAULT = "machine_fault"
    MATERIAL_DEFECT = "material_defect"
    PROGRAM_ERROR = "program_error"
    OUT_OF_TOLERANCE = "out_of_tolerance"
    SUPPLIER_DAMAGE = "supplier_damage"
    TRANSPORT_DAMAGE = "transport_damage"
    WRONG_SPEC = "wrong_spec"
    OTHER = "other"
