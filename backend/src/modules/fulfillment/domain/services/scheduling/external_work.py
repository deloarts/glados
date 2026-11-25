"""Which lot positions are external work: positions that go to a supplier
for an outside process such as hardening or galvanizing. The schedule walk
forecasts each of them, and the procurement list of external work shows
them. The production lot repository mirrors these rules in SQL."""

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import date
from datetime import timedelta

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.policies.wait_after import wait_days
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    compute_position_due_dates,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import position_lead_days
from src.modules.fulfillment.domain.services.scheduling.walk_context import ExternalForecast
from src.modules.fulfillment.domain.services.scheduling.walk_context import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_chain_external_forecasts,
)
from src.modules.fulfillment.domain.value_objects.external_work import ExternalWorkAlert
from src.modules.fulfillment.domain.value_objects.external_work import ExternalWorkStage
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus

# A completed or canceled position sends nothing to a supplier any more.
_CLOSED_POSITION_STATUSES = frozenset({LotPositionStatus.COMPLETED, LotPositionStatus.CANCELED})


def is_outsourced_unassigned(position: LotPosition) -> bool:
    """An UNASSIGNED position with a fabrication step whose method is
    usually outsourced, so it is expected to go to a supplier once someone
    assigns it."""
    return position.kind == LotPositionKind.UNASSIGNED and any(
        step.role == StepRole.FABRICATION and step.fabrication_method_required_external
        for step in position.steps
    )


def position_has_external_work(position: LotPosition) -> bool:
    """An open position that is EXTERNAL or MIXED, or an outsourced
    UNASSIGNED one."""
    if position.status in _CLOSED_POSITION_STATUSES:
        return False
    if position.kind in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED):
        return True
    return is_outsourced_unassigned(position)


@dataclass(frozen=True)
class ExternalWorkChain:
    """One lot's open positions described for the walk, read before the
    walk runs, which of them are external work, the lot's target date and
    the minutes of work left on each position done in house."""

    lot_id: int
    positions: tuple[PredecessorPosition, ...]
    external_position_ids: frozenset[int]
    target_date: date | None = None
    remaining_minutes_by_position: Mapping[int, int] = field(default_factory=dict)


def latest_pickup_dates(chain: ExternalWorkChain, safety_margin_days: int) -> dict[int, date]:
    """The latest day each external work position of the chain can leave
    for the supplier without making the lot miss its target date, by
    position id.

    It counts back from the target date, less the safety margin, the way
    Auto-Plan dates its positions (compute_position_due_dates): a position
    done in house takes its remaining minutes in whole days of eight hours,
    at least one, and an external position its lead days, all counted as
    calendar days and without any waiting at the machines. The wait after a
    position done in house counts in whole days too. An external position
    must be back when the position after it has to start, so it leaves its
    lead days before that. A completed position whose wait still runs has
    no work left and counts nothing. A lot without a target date has no
    latest day."""
    if chain.target_date is None:
        return {}
    open_positions = [p for p in chain.positions if not p.completed]
    lead_days_by_sequence: dict[int, int] = {}
    wait_days_by_sequence: dict[int, int] = {}
    for position in open_positions:
        if position.position_id in chain.external_position_ids:
            lead_days_by_sequence[position.sequence] = position.lead_days or 0
        else:
            lead_days_by_sequence[position.sequence] = position_lead_days(
                "internal", chain.remaining_minutes_by_position.get(position.position_id, 0), 0
            )
        wait_days_by_sequence[position.sequence] = wait_days(position.wait_after_minutes)
    due_by_sequence = compute_position_due_dates(
        [p.sequence for p in open_positions],
        lead_days_by_sequence,
        chain.target_date - timedelta(days=safety_margin_days),
        wait_days_by_sequence,
    )
    latest: dict[int, date] = {}
    for position in open_positions:
        due = due_by_sequence.get(position.sequence)
        if position.position_id in chain.external_position_ids and due is not None:
            latest[position.position_id] = due - timedelta(
                days=lead_days_by_sequence[position.sequence]
            )
    return latest


def forecast_external_work(
    chains: list[ExternalWorkChain],
    placed_end_by_position: dict[int, date | None],
    response_time_days: int,
    safety_margin_days: int,
) -> list[ExternalForecast]:
    """The forecast of every external work position of the chains, ordered
    by lot and position, with its latest pickup day and the day it is back
    at the latest when it leaves then. `placed_end_by_position`
    holds the internal positions' ends from the walk that just ran; a
    position without an order in it reads its stored end."""
    forecasts: list[ExternalForecast] = []
    for chain in sorted(chains, key=lambda c: c.lot_id):
        by_position = resolve_chain_external_forecasts(
            chain.positions, placed_end_by_position, response_time_days
        )
        latest = latest_pickup_dates(chain, safety_margin_days)
        lead_days = {p.position_id: p.lead_days or 0 for p in chain.positions}
        for position_id, forecast in sorted(by_position.items()):
            if position_id not in chain.external_position_ids:
                continue
            pickup = latest.get(position_id)
            forecasts.append(
                replace(
                    forecast,
                    latest_pickup_date=pickup,
                    latest_delivery_date=(
                        pickup + timedelta(days=lead_days[position_id]) if pickup else None
                    ),
                )
            )
    return forecasts


def inputs_ready(position: LotPosition, lot: ProductionLot) -> bool:
    """Whether the pieces of the position are already there to go out:
    every earlier position of the lot is closed, or for the first position
    the raw material has arrived."""
    if position.sequence <= 1:
        return lot.source_delivery_date is not None
    return all(
        earlier.status in _CLOSED_POSITION_STATUSES
        for earlier in lot.positions
        if earlier.sequence < position.sequence
    )


def external_work_alert(
    position: LotPosition, *, ready_now: bool, today: date
) -> ExternalWorkAlert | None:
    """The alert the procurement list shows for the position, mirrored by
    the repository's only-critical filter. A position some of whose pieces
    went to the supplier already is under way and never overdue."""
    latest = position.latest_pickup_date
    if latest is None:
        return ExternalWorkAlert.NO_TARGET_DATE
    if position.provisioned_quantity <= 0 and latest < today:
        return ExternalWorkAlert.OVERDUE
    ready_from = position.planned_pickup_date
    if not ready_now and ready_from is not None and ready_from > latest:
        return ExternalWorkAlert.NOT_READY_IN_TIME
    return None


__all__ = [
    "ExternalWorkAlert",
    "ExternalWorkChain",
    "ExternalWorkStage",
    "external_work_alert",
    "forecast_external_work",
    "inputs_ready",
    "is_outsourced_unassigned",
    "latest_pickup_dates",
    "position_has_external_work",
]
