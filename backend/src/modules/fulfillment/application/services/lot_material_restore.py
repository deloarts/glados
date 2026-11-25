"""
Gives lots their material need back when the production setting
external_first_step_needs_no_material is turned off. A lot awaiting its first
step, or sourced by the supplier of that step, then needs our material again
and starts over as a new lot would: pending while its source item waits for
approval, otherwise with a demand for what it still lacks
(lot_material_demand.missing_material).

The demand restores the lot's own material need, which it had before the
setting took it away, so it is not new work and needs no active project.
The lots are locked through the reconciler's lock plan before they are read
again, and the reconciler derives the new demands; the caller commits.
"""

from datetime import datetime

from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_material_demand import missing_material
from src.modules.fulfillment.application.services.source_item_demand_factory import (
    build_source_item_demand,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialSupply
from src.modules.fulfillment.domain.services.lot_material_rules import initial_status
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.source_approval_status import (
    SUPPLIER_MATERIAL_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.shared_kernel.domain.services.changelog_service import append_changelog

RESTORE_REASON = "external first step no longer brings the material"


class RestoreLotMaterial:
    """See the module docstring."""

    def __init__(
        self,
        lots: IProductionLotRepository,
        demands: ISourceItemDemandRepository,
        allocations: ISourceItemAllocationRepository,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._lots = lots
        self._demands = demands
        self._allocations = allocations
        self._reconciler = reconciler

    async def restore(self, actor: User, now: datetime, *, approval_required: bool) -> int:
        """Restores every live lot in a supplier material status and returns
        how many it restored."""
        lot_ids = await self._candidate_ids()
        if not lot_ids:
            return 0
        self._reconciler.touch_lots(lot_ids)
        await self._reconciler.lock_touched()
        restored = 0
        for lot in await self._lots.get_by_ids(lot_ids, refresh=True):
            if not _restorable(lot):
                continue
            await self._restore_one(actor, lot, now, approval_required=approval_required)
            restored += 1
        await self._reconciler.run(actor, now, reason=RESTORE_REASON)
        return restored

    async def _candidate_ids(self) -> list[int]:
        ids: set[int] = set()
        for status in sorted(SUPPLIER_MATERIAL_STATUSES):
            _, lots = await self._lots.get_multi(LotFilterDto(source_approval_status=status))
            ids.update(lot.id for lot in lots if _restorable(lot))
        return sorted(ids)

    async def _restore_one(
        self, actor: User, lot: ProductionLot, now: datetime, *, approval_required: bool
    ) -> None:
        lot.source_approval_status = initial_status(
            MaterialSupply.OURS,
            approval_required=approval_required,
            source_is_item=lot.source_item_id is not None,
        )
        lot.changed = now
        lot.changes = append_changelog(
            lot.changes,
            actor.full_name,
            f"Material needed again ({RESTORE_REASON}); source "
            f"{lot.source_approval_status.value.replace('_', ' ')}.",
        )
        if lot.source_approval_status != SourceApprovalStatus.PENDING:
            await self._demand_what_is_missing(actor, lot)
        await self._lots.save(lot)

    async def _demand_what_is_missing(self, actor: User, lot: ProductionLot) -> None:
        quantity, unit, items_per_unit = await missing_material(
            lot, self._demands, self._allocations
        )
        if not quantity_gt(quantity, 0.0):
            return
        demand = await self._demands.save(
            build_source_item_demand(
                lot,
                actor,
                quantity=quantity,
                unit=unit,
                items_per_unit=items_per_unit,
                high_priority=False,
                notify_on_delivery=False,
                note=None,
                desired_delivery_date=None,
            )
        )
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand.id], created=True)
        lot.input_demand_id = demand.id
        lot.changes = append_changelog(
            lot.changes, actor.full_name, f"Linked source item demand #{demand.id}."
        )


def _restorable(lot: ProductionLot) -> bool:
    """A live lot in a supplier material status without a demand of its own."""
    return (
        lot.source_approval_status in SUPPLIER_MATERIAL_STATUSES
        and lot.status not in TERMINAL_LOT_STATUSES
        and lot.input_demand_id is None
    )
