"""
What happens to a batch of pieces rejected while booking a supplier
delivery. Stored as a plain string column (order_item_delivery_table.
rejection_outcome) and validated at the API boundary by the schema layer,
not by a DB enum type, so a later addition (e.g. a concession outcome
that accepts the pieces as-is with approval) needs no schema change.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class RejectionOutcome(StrValueEnum):
    """What happens to rejected pieces: the supplier sends replacements
    under the same order line (REDELIVER), or the pieces are gone for
    good and the shortfall is covered some other way (LOST)."""

    REDELIVER = "redeliver"
    LOST = "lost"
