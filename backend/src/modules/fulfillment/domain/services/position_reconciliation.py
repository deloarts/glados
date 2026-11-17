"""The piece balance of each lot position: where every piece that reached it
went.

A position's pieces arrive from its predecessor's good pieces, or for
position 1 from the lot's quantity and the raw material that arrived. They
leave as good pieces (accepted by its production orders, or delivered by
its supplier), as scrap, as rework sent to a rework lot, or as pieces lost
at a supplier's receipt; the rest is still work in process. So arrived =
good + scrap + rework + lost + WIP. WIP never goes below zero, so a position
that booked more than reached it shows the excess as a negative difference
instead. The produced quantity is good plus scrap, as ISO 22400 defines it.
"""

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.lot_rules import available_input


@dataclass(frozen=True)
class PositionBalance:
    position_id: int
    sequence: int
    kind: str
    arrived: float
    good: float
    scrap: float
    rework: float
    lost: float
    wip: float
    # Zero when every piece is accounted for; negative when the position
    # booked more than reached it.
    difference: float
    # ISO 22400 produced quantity: good plus scrap.
    produced: float


def balance_positions(
    positions: Sequence[LotPosition],
    lot_quantity: float,
    orders_by_position: Mapping[int, Sequence[ProductionOrder]],
    lost_by_position: Mapping[int, float],
    raw_material_arrived: float | None,
) -> list[PositionBalance]:
    """The balance of every position, in sequence order. `orders_by_position`
    holds each position's production orders with their completions,
    `lost_by_position` the pieces its supplier line lost at receipt, and
    `raw_material_arrived` what position 1 may draw on (None when its input
    is not bounded by raw material)."""
    ordered = sorted(positions, key=lambda p: p.sequence)
    balances = []
    for position in ordered:
        completions = [
            c for order in orders_by_position.get(position.id, ()) for c in order.completions
        ]
        arrived = available_input(
            list(ordered),
            lot_quantity,
            position.sequence,
            raw_material_arrived if position.sequence <= 1 else None,
        )
        good = _rounded(
            sum(c.quantity_accepted for c in completions)
            + (position.order_item_quantity_delivered or 0.0)
            + position.closed_lines_delivered
        )
        scrap = _rounded(sum(c.quantity_scrap for c in completions))
        rework = _rounded(sum(c.quantity_rework for c in completions))
        lost = _rounded(lost_by_position.get(position.id, 0.0))
        accounted = good + scrap + rework + lost
        wip = _rounded(max(arrived - accounted, 0.0))
        balances.append(
            PositionBalance(
                position_id=position.id,
                sequence=position.sequence,
                kind=position.kind,
                arrived=_rounded(arrived),
                good=good,
                scrap=scrap,
                rework=rework,
                lost=lost,
                wip=wip,
                difference=_rounded(arrived - accounted - wip),
                produced=_rounded(good + scrap),
            )
        )
    return balances


def _rounded(value: float) -> float:
    """Sums of float pieces rounded to the stored precision, so a balance
    that holds shows a difference of exactly zero."""
    return round(value, 6) + 0.0
