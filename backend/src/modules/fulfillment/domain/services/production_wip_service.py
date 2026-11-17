"""
Pure computation for the live WIP (work-in-progress) read model:
because every LotPosition tracks `quantity_completed`, the current
location of every piece in production is derivable per lot, pieces not
yet completed by position 1 are raw/waiting, pieces completed by
position N but not N+1 are at stage N+1, pieces completed by the last
position are finished. No I/O, takes a pre-fetched ProductionLot
(with its positions already populated by the repository) and returns
plain dataclasses, mirroring lot_rules.py's pure functions.

Scope note: this is quantity-level tracking only, no provision-based
sub-split of EXTERNAL positions into awaiting-dispatch vs at-supplier
(that's LotPositionProvision, out of scope here).
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.fulfillment.domain.entities.production_lot import ProductionLot


@dataclass(frozen=True)
class WipStage:
    """One LotPosition's piece-count state within a lot's WIP breakdown."""

    position_id: int
    sequence: int
    kind: str
    status: str
    quantity: float
    quantity_completed: float
    machine_names: list[str] = field(default_factory=list)  # INTERNAL positions
    supplier_name: str = ""  # EXTERNAL positions


@dataclass(frozen=True)
class WipSummary:
    raw_count: float
    finished_count: float
    stages: list[WipStage]


def compute_wip_summary(lot: ProductionLot) -> WipSummary:
    """Raw/waiting = lot quantity minus position-1's quantity_completed, never
    below zero: after pieces are removed further down the chain, position 1
    keeps its larger quantity and can complete more than the lot quantity.
    Finished = the last position's quantity_completed (mirrors
    ProductionLot.quantity_completed). Empty-positions lots (should not
    happen for PARTIALLY_PLANNED+ lots, but handled defensively) report the full
    lot quantity as raw and nothing finished."""
    positions = sorted(lot.positions, key=lambda p: p.sequence)

    stages = [
        WipStage(
            position_id=p.id,
            sequence=p.sequence,
            kind=p.kind,
            status=p.status,
            quantity=p.quantity,
            quantity_completed=p.quantity_completed,
            machine_names=list(
                dict.fromkeys(po.machine_internal_name for po in p.production_orders)
            ),
            supplier_name=p.supplier_name,
        )
        for p in positions
    ]

    first_completed = positions[0].quantity_completed if positions else 0.0
    last_completed = positions[-1].quantity_completed if positions else 0.0

    return WipSummary(
        raw_count=max(0.0, lot.quantity - first_completed),
        finished_count=last_completed,
        stages=stages,
    )
