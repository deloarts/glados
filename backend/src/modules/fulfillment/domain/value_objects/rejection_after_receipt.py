"""Pieces rejected after they were accepted at goods receipt, such as hidden
damage found when the goods are unpacked or inspected.

A correction of a delivery row that carries one takes the accepted pieces
back as rejected ones, with the classified reason (a ScrapReason value), what
happens to them (RejectionOutcome) and an optional note, instead of taking
them back as a miscount.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome


@dataclass(frozen=True)
class RejectionAfterReceipt:
    reason: str
    outcome: RejectionOutcome
    note: str | None = None
