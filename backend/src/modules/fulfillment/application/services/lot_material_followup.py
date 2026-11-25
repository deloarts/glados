"""
The material follow-up of the lifecycle reconciler's run. When the run moves
who does a lot's first position, the lot's raw material demand follows the
rules of lot_material_rules.py: a supplier who takes the position over
brings the material, so the lot gets the matching status and its live demand
is settled; a MIXED position demands only what it makes in house; and a
position that comes back to us gives a lot that needed no material its
demand back, or puts it into approval, as a new lot would start.

It acts only on lots whose first position changed kind in the run, or is
MIXED and had a line touched, so a demand a user ended or resized is left
alone by every write that does not change the position. A lot in a supplier
status has no input demand: a settled demand, and an ended one the lot still
links, is unlinked, so a later demand or source switch starts clean, while
the old demand stays with the lot as its history. A new demand restores the
lot's own material need, so it is not new work and needs no active project.

Finding the lots is a scan of what the run already read and wrote, so a run
that moves no first position costs nothing more. Only then is the setting
read, and with the setting off the follow-up does nothing. The demand and the
order lines a settle or resize writes are locked before they are read; the
lock step normally holds them already (lifecycle_reconciler.py), and a late
lock covers the rest.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Protocol

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import FollowUpTouches
from src.modules.fulfillment.application.services.lot_material_demand import LineRelease
from src.modules.fulfillment.application.services.lot_material_demand import LotMaterialDemand
from src.modules.fulfillment.application.services.lot_material_demand import demand_missing_material
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import SnapshotDerivation
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lot_material_rules import DemandAction
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialDecision
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialSupply
from src.modules.fulfillment.domain.services.lot_material_rules import decide_material
from src.modules.fulfillment.domain.services.lot_material_rules import first_position
from src.modules.fulfillment.domain.services.lot_material_rules import first_position_supply
from src.modules.fulfillment.domain.services.lot_material_rules import in_house_need
from src.modules.fulfillment.domain.services.lot_material_rules import predicts_supplier_material
from src.modules.fulfillment.domain.services.lot_material_rules import supplier_share
from src.modules.fulfillment.domain.services.lot_material_rules import tracks_material
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.source_approval_status import (
    SUPPLIER_MATERIAL_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    LIVE_SOURCE_DEMAND_STATUSES,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.changelog_service import append_changelog

_A = LifecycleAggregate

_REASONS: dict[MaterialSupply, str] = {
    MaterialSupply.OURS: "first position made in house",
    MaterialSupply.SHARED: "first position shared with a supplier",
    MaterialSupply.SUPPLIER: "first position made by a supplier",
    MaterialSupply.SUPPLIER_EXPECTED: "first position expected to go to a supplier",
}


class ProductionSettingsReader(Protocol):
    async def get_production(self) -> AdminProductionSettings: ...


@dataclass(frozen=True)
class MaterialChange:
    """A lot whose first position the run moved, with who now brings its
    material and how many pieces it makes from ours."""

    lot: ProductionLot
    supply: MaterialSupply
    need: float


def _follows_material(lot: ProductionLot) -> bool:
    return lot.status not in TERMINAL_LOT_STATUSES and tracks_material(lot)


def first_position_changes(
    changes: Sequence[FieldChange],
    snapshot: LifecycleSnapshot,
    derivation: SnapshotDerivation,
    touched: AggregateIds,
) -> list[MaterialChange]:
    """The live lots tracking material whose first position changed kind in
    the run, or is MIXED and had a line touched, by lot id. Reads nothing."""
    kind_changed = {
        c.id for c in changes if c.aggregate is _A.LOT_POSITIONS and c.field is LifecycleField.KIND
    }
    line_positions = {
        line.lot_position_id
        for line_id in touched.get(_A.ORDER_ITEMS)
        if (line := snapshot.order_items.get(line_id)) is not None
        and line.lot_position_id is not None
    }
    if not kind_changed and not line_positions:
        return []
    found: list[MaterialChange] = []
    for lot in sorted(snapshot.lots.values(), key=lambda lot: lot.id):
        position = first_position(lot)
        if position is None or not _follows_material(lot):
            continue
        derived = derivation.positions.get(position.id)
        if derived is None:
            continue
        kind = derived.kind.value
        if position.id not in kind_changed and not (
            kind == LotPositionKind.MIXED and position.id in line_positions
        ):
            continue
        facts = derived.kind.facts
        supply = first_position_supply(kind, predicted=predicts_supplier_material(position.steps))
        found.append(
            MaterialChange(
                lot, supply, in_house_need(supply, facts.quantity, supplier_share(facts))
            )
        )
    return found


def material_lock_demands(snapshot: LifecycleSnapshot, touched: AggregateIds) -> frozenset[int]:
    """The live raw material demands of the live lots whose first position
    the touched rows reach: the position, a line of it or a production order
    of it, which is all a position's kind reads. Reads nothing."""
    positions = set(touched.get(_A.LOT_POSITIONS))
    positions.update(
        line.lot_position_id
        for line_id in touched.get(_A.ORDER_ITEMS)
        if (line := snapshot.order_items.get(line_id)) is not None
        and line.lot_position_id is not None
    )
    positions.update(
        order.lot_position_id
        for order_id in touched.get(_A.PRODUCTION_ORDERS)
        if (order := snapshot.production_orders.get(order_id)) is not None
    )
    if not positions:
        return frozenset()
    found: set[int] = set()
    for lot in snapshot.lots.values():
        position = first_position(lot)
        if (
            position is not None
            and position.id in positions
            and _follows_material(lot)
            and lot.input_demand_id is not None
            and lot.demand_status in LIVE_SOURCE_DEMAND_STATUSES
        ):
            found.add(lot.input_demand_id)
    return frozenset(found)


@dataclass
class _Touches:
    demands: set[int] = field(default_factory=set)
    created: set[int] = field(default_factory=set)
    lines: set[int] = field(default_factory=set)

    def result(self) -> FollowUpTouches:
        return FollowUpTouches(
            demands=frozenset(self.demands),
            created=frozenset(self.created),
            lines=frozenset(self.lines),
        )


class LotMaterialFollowUp:
    """The reconciler's MaterialFollowUp; see the module docstring."""

    def __init__(
        self,
        settings: ProductionSettingsReader,
        lots: IProductionLotRepository,
        demands: ISourceItemDemandRepository,
        allocations: ISourceItemAllocationRepository,
        line_release: LineRelease,
    ) -> None:
        self._settings = settings
        self._lots = lots
        self._demands = demands
        self._allocations = allocations
        self._material = LotMaterialDemand(demands, allocations, line_release)

    def lock_demands(self, snapshot: LifecycleSnapshot, touched: AggregateIds) -> frozenset[int]:
        return material_lock_demands(snapshot, touched)

    async def apply(
        self,
        actor: User,
        now: datetime,
        *,
        changes: Sequence[FieldChange],
        snapshot: LifecycleSnapshot,
        derivation: SnapshotDerivation,
        touched: AggregateIds,
        lock_plan: LockPlan,
    ) -> FollowUpTouches:
        found = first_position_changes(changes, snapshot, derivation, touched)
        if not found:
            return FollowUpTouches()
        settings = await self._settings.get_production()
        if not settings.external_first_step_needs_no_material:
            return FollowUpTouches()
        demands = await self._read({c.lot.input_demand_id for c in found})
        acting = {
            demand.id
            for change in found
            if (demand := _live(demands, change.lot)) is not None
            and _decide(change, demand, settings).action
            in (DemandAction.SETTLE, DemandAction.RESIZE)
        }
        if acting:
            demands.update(await self._lock_and_read(lock_plan, acting))
        touches = _Touches()
        for change in found:
            await self._follow(actor, now, change, _live(demands, change.lot), settings, touches)
        return touches.result()

    async def _read(self, ids: Iterable[int | None]) -> dict[int, SourceItemDemandItem]:
        wanted = sorted(i for i in ids if i is not None)
        if not wanted:
            return {}
        return {d.id: d for d in await self._demands.get_by_ids(wanted, refresh=True)}

    async def _lock_and_read(
        self, lock_plan: LockPlan, demand_ids: set[int]
    ) -> dict[int, SourceItemDemandItem]:
        """Locks the demands with the lines they are allocated on and reads
        them again. An allocation writer locks a demand before it adds to
        it, so a line found under the demand locks that was not found before
        is one added in between, and it is locked as well."""
        lines: set[int] = set()
        while True:
            for demand_id in sorted(demand_ids):
                lines |= await self._material.line_ids(demand_id)
            ids = AggregateIds.of({_A.ORDER_ITEMS: lines, _A.SOURCE_DEMANDS: demand_ids})
            if ids.issubset(lock_plan.held):
                return await self._read(demand_ids)
            await lock_plan.acquire_late(ids)

    async def _follow(
        self,
        actor: User,
        now: datetime,
        change: MaterialChange,
        demand: SourceItemDemandItem | None,
        settings: AdminProductionSettings,
        touches: _Touches,
    ) -> None:
        lot = change.lot
        decision = _decide(change, demand, settings)
        reason = _REASONS[change.supply]
        changed = False
        if decision.status != lot.source_approval_status:
            lot.changes = append_changelog(
                lot.changes,
                actor.full_name,
                f"Source approval: {_text(lot.source_approval_status.value)} → "
                f"{_text(decision.status.value)} ({reason}).",
            )
            lot.source_approval_status = decision.status
            changed = True
        if demand is not None and decision.action in (DemandAction.SETTLE, DemandAction.RESIZE):
            touches.lines |= await self._material.line_ids(demand.id)
            touches.demands.add(demand.id)
            if decision.action is DemandAction.SETTLE:
                await self._material.settle(actor, demand, now, reason=reason)
            else:
                await self._material.resize(actor, demand, decision.quantity, now, reason=reason)
        if decision.action is DemandAction.CREATE:
            created = await demand_missing_material(
                actor, lot, self._demands, self._allocations, at_most=decision.quantity
            )
            if created is not None:
                touches.created.add(created.id)
                changed = True
        if lot.input_demand_id is not None and (
            decision.action is DemandAction.SETTLE or decision.status in SUPPLIER_MATERIAL_STATUSES
        ):
            lot.changes = append_changelog(
                lot.changes,
                actor.full_name,
                f"Unlinked source item demand #{lot.input_demand_id} ({reason}).",
            )
            lot.input_demand_id = None
            lot.demand_status = None
            changed = True
        if changed:
            lot.changed = now
            await self._lots.save(lot)


def _live(
    demands: dict[int, SourceItemDemandItem], lot: ProductionLot
) -> SourceItemDemandItem | None:
    """The lot's input demand while it still waits for material."""
    demand = demands.get(lot.input_demand_id) if lot.input_demand_id is not None else None
    if demand is None or demand.status not in LIVE_SOURCE_DEMAND_STATUSES:
        return None
    return demand


def _decide(
    change: MaterialChange,
    demand: SourceItemDemandItem | None,
    settings: AdminProductionSettings,
) -> MaterialDecision:
    return decide_material(
        change.supply,
        current=change.lot.source_approval_status,
        live_demand_quantity=demand.quantity if demand is not None else None,
        need=change.need,
        approval_required=settings.require_source_item_approval,
        source_is_item=change.lot.source_item_id is not None,
    )


def _text(status: str) -> str:
    return status.replace("_", " ")
