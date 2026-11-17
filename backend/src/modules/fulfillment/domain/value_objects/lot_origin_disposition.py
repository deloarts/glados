"""
Distinguishes whether a follow-up lot spawned from a rejected inspection
reworks the same pieces or replaces them with a freshly-built run. See
LotOriginDisposition for the two values and ProductionLot.origin_lot_id/
origin_disposition for how a lot links back to the one it was spawned from.
"""

from enum import Enum
from enum import unique


@unique
class LotOriginDisposition(str, Enum):
    """How a follow-up lot relates to the lot it was spawned from, when an
    inspection completion rejects pieces (see ProductionLot.origin_lot_id/
    origin_disposition and record_production_order_completion.py). REWORK:
    the rejected pieces themselves get reworked (source_made_item_id set
    to the same made item, an alteration run with no new raw material).
    REPLACEMENT: the rejected pieces are scrapped and replaced with a
    freshly-built run (normal raw-material sourcing)."""

    REWORK = "rework"
    REPLACEMENT = "replacement"
