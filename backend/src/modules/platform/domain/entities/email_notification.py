"""
Queued entry for a user's email digest. The notification handler writes one
when a demand of any family (bought, made or source item) that asked for a
delivery notice is fulfilled, addressed to the demand's creator, and one
for the bundled mentions and todo assignments of a meeting, addressed to
the user they concern.
"""

from dataclasses import dataclass
from typing import Literal

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class EmailNotification(Entity):
    reason: Literal["delivered", "meeting"]
    receiver_id: int  # → User to notify

    # The fulfilled demand, in whichever family it belongs to. Set for a
    # delivery.
    demand_item_id: int | None
    # The order item that delivered a bought item demand, or None when the
    # demand was covered some other way or belongs to another family.
    order_item_id: int | None
    # The meeting and the sentence that sums up its activity, for a meeting.
    meeting_id: int | None = None
    message: str | None = None
