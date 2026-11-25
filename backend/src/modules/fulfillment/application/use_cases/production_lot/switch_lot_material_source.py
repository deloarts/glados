"""
Lets a user override a lot's material source after creation, it's seeded
from the made item's own bought_item_id/source_item_id at CreateLot time, but
the actual source for a specific production run can legitimately differ
(e.g. switching into a rework of an existing MadeItem). A lot's demand is
auto-created here too (mirrors CreateLot), so switching to a new bought/source
source replaces the old demand, once the caller confirmed it with
`confirm_replace_demand=True`. An open demand is canceled, as every demand
cancel does (LotHasOpenDemandError asks first). A demand already allocated
or ordered keeps what reached it and releases the rest of its allocations,
as a demand marked fulfilled by hand does, and the new source is demanded
for what is still missing (LotHasPlacedDemandError asks first, so the
client can show what arrived); the order lines it released stay with
purchasing to cancel or close short. A fulfilled demand leaves nothing to
switch and is refused. The new demand is new work for the lot's project,
which must be active, and the new source an item new work may name.
A completed, canceled or scrapped lot uses no more material and is refused
(409), also for a holder of manage:lots, who may otherwise edit an ended lot.
The switch is irreversible, so it checks the lot's edit version.

A source switch is also a new source item approval decision (see
source_approval_status.py): source_approval_status is always re-derived
for the NEW source (pending if require_source_item_approval is on and the
new source is a source item, not_required otherwise) and every decision
field is cleared: an old approval/rejection was for the OLD source, it
says nothing about this one. A lot whose first position a supplier does, or
is expected to do, brings no material of ours and takes the matching status
with no demand instead, and a MIXED first position demands only what it
makes in house (lot_material_rules.py).
"""

from datetime import datetime
from typing import Any

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.allocation_locks import lock_for_allocation
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_material_demand import LotMaterialDemand
from src.modules.fulfillment.application.services.source_item_demand_factory import (
    build_source_item_demand,
)
from src.modules.fulfillment.application.use_cases._demand_family.unarrived_release import (
    UnarrivedLineRelease,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import LotHasOpenDemandError
from src.modules.fulfillment.domain.errors import LotHasPlacedDemandError
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotRawMaterialAlreadyLinkedError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialSupply
from src.modules.fulfillment.domain.services.lot_material_rules import capped_to_in_house
from src.modules.fulfillment.domain.services.lot_material_rules import initial_status
from src.modules.fulfillment.domain.services.lot_material_rules import lot_supply
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_lot_action
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
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
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# The statuses in which the switch leaves the lot without a demand: approval
# creates it later, or the supplier of the first position brings the material.
_NO_DEMAND_YET = frozenset(
    {
        SourceApprovalStatus.PENDING,
        SourceApprovalStatus.AWAITING_FIRST_STEP,
        SourceApprovalStatus.SUPPLIER_SOURCED,
    }
)


class SwitchLotMaterialSource:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        bought_item_repo: IBoughtItemQueries,
        source_item_repo: ISourceItemQueries,
        made_item_repo: IMadeItemQueries,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        settings_repo: IFulfillmentSettingsRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        project_repo: IProjectQueries,
        line_release: UnarrivedLineRelease[Any],
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        """`line_release` cuts a placed raw material demand's line
        allocations down to the pieces that reached it."""
        self._lots = lot_repo
        self._bought_items = bought_item_repo
        self._source_items = source_item_repo
        self._made_items = made_item_repo
        self._demands = source_item_demand_repo
        self._allocations = source_item_allocation_repo
        self._settings = settings_repo
        self._recompute = recompute_schedule
        self._projects = project_repo
        self._line_release = line_release
        self._material = LotMaterialDemand(
            source_item_demand_repo, source_item_allocation_repo, line_release
        )
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, lot_id: int, cmd: SwitchLotMaterialSourceCommand
    ) -> LotResult:
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )

        LotRules.assert_can_update(actor, lot)

        # The new demand is new work on the lot's project: shared before the
        # lifecycle locks, as every writer of new work takes it.
        await self._projects.lock_for_share([lot.project_id])
        # The lot, the demand it replaces and the order lines that demand
        # holds are locked before the checks, in the one lock order. A demand
        # linked, or a line allocated, in between was not locked, so the
        # request is refused for a retry.
        read_demand_id = lot.input_demand_id
        read_line_ids: set[int] = set()
        if read_demand_id is not None:
            read_line_ids = await self._line_release.line_ids(read_demand_id)
            await lock_for_allocation(
                self._reconciler,
                LifecycleAggregate.SOURCE_DEMANDS,
                [read_demand_id],
                order_item_ids=sorted(read_line_ids),
                lot_ids=[lot_id],
            )
        else:
            await self._reconciler.lock_touched(
                also=AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]})
            )
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        changed = ConcurrentModificationError(
            f"Lot #{lot_id}'s source item demand changed while its material source was "
            "being switched. Reload and try again."
        )
        if lot.input_demand_id != read_demand_id:
            raise changed
        if read_demand_id is not None and not (
            await self._line_release.line_ids(read_demand_id) <= read_line_ids
        ):
            raise changed
        # An ended lot uses no more material, so it takes no new demand.
        assert_lot_action(LifecycleAction.SWITCH_SOURCE, lot, actor)
        assert_edit_version(lot, cmd.expected_edit_version, what=f"Lot #{lot.id}")

        old_demand = await self._replaceable_demand(lot, cmd)
        LotRules.assert_at_most_one_material_source(
            cmd.bought_item_id, cmd.source_item_id, cmd.made_item_id
        )
        await self._assert_new_source_demandable(cmd)

        now = now_utc()

        # What the new source still has to bring, in the old demand's unit;
        # None means the whole lot, as for a lot without a placed demand.
        missing: tuple[float, str, float] | None = None
        if old_demand is not None:
            missing = await self._settle_old_demand(actor, old_demand, now)

        # A new source is a new approval decision, so a client still holding
        # the old one gets a 409 when it approves or rejects.
        bump_edit_version(lot)
        lot.source_bought_item_id = cmd.bought_item_id
        lot.source_item_id = cmd.source_item_id
        lot.source_made_item_id = cmd.made_item_id
        lot.input_demand_id = None
        lot.changed = now
        lot.changes = append_changelog(lot.changes, actor.full_name, "Material source switched.")

        supply = await self._reset_source_approval(lot, cmd)

        if (
            (cmd.bought_item_id is not None or cmd.source_item_id is not None)
            and lot.source_approval_status not in _NO_DEMAND_YET
            and (missing is None or quantity_gt(missing[0], 0.0))
        ):
            await self._assert_project_active(lot)
            await self._create_source_item_demand(actor, lot, now, missing, supply)

        await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.LOT_MATERIAL_SOURCE_SWITCHED,
                "lot",
                "Material source switched.",
                payload={
                    "bought_item_id": cmd.bought_item_id,
                    "source_item_id": cmd.source_item_id,
                    "made_item_id": cmd.made_item_id,
                },
            )
        )
        await self._reconciler.run(actor, now)
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(f"switching material source for lot #{lot_id}; the switch itself is committed."),
        )

        log.info(f"Switched material source for lot #{lot_id}.")
        result_lot = await self._lots.get_by_id(lot_id)
        assert result_lot is not None
        return LotMapper.to_result(result_lot)

    async def _replaceable_demand(
        self, lot: ProductionLot, cmd: SwitchLotMaterialSourceCommand
    ) -> SourceItemDemandItem | None:
        """The lot's current source item demand, which the switch replaces
        once the caller confirmed it. A fulfilled one leaves nothing to
        switch."""
        if lot.input_demand_id is None:
            return None
        old_demand = await self._demands.get_by_id(lot.input_demand_id)
        if old_demand is None or old_demand.status in (
            SourceItemDemandStatus.FULFILLED,
            SourceItemDemandStatus.CANCELED,
        ):
            raise LotRawMaterialAlreadyLinkedError(
                f"Lot #{lot.id}'s raw material demand (#{lot.input_demand_id}) is fulfilled: "
                "its material has all arrived, so nothing is left to order from another source."
            )
        if cmd.confirm_replace_demand:
            return old_demand
        if old_demand.status == SourceItemDemandStatus.OPEN:
            raise LotHasOpenDemandError(
                f"Lot #{lot.id} has an open source item demand (#{lot.input_demand_id}); "
                "switching the source will cancel it and create a new one, resubmit "
                "with confirm_replace_demand=True to proceed."
            )
        raise LotHasPlacedDemandError(
            f"Lot #{lot.id}'s source item demand (#{lot.input_demand_id}) is already allocated "
            "or ordered; switching keeps what arrived, releases the rest and demands what is "
            "missing from the new source. Resubmit with confirm_replace_demand=True to proceed."
        )

    async def _settle_old_demand(
        self, actor: User, demand: SourceItemDemandItem, now: datetime
    ) -> tuple[float, str, float] | None:
        """Ends the old demand and returns what the new source still has to
        bring as (quantity, unit, items per unit), or None for the whole lot
        (lot_material_demand.py)."""
        arrived = await self._material.settle(actor, demand, now, reason="source switched")
        if quantity_gt(arrived, 0.0):
            return (max(demand.quantity - arrived, 0.0), demand.unit, demand.items_per_unit)
        return None

    async def _assert_project_active(self, lot: ProductionLot) -> None:
        assert_project_active(
            found_or_raise(
                await self._projects.get_by_id(lot.project_id),
                ProjectNotFoundError,
                f"Project #{lot.project_id} not found.",
            ),
            work="material demands",
        )

    async def _assert_new_source_demandable(self, cmd: SwitchLotMaterialSourceCommand) -> None:
        """The new source must exist and be an item new work may name."""
        if cmd.bought_item_id is not None:
            bought_item = found_or_raise(
                await self._bought_items.get_by_id(cmd.bought_item_id),
                BoughtItemNotFoundError,
                f"Bought item #{cmd.bought_item_id} not found.",
            )
            BoughtItemCatalogueRules.assert_item_demandable(bought_item)

        if cmd.source_item_id is not None:
            source_item = found_or_raise(
                await self._source_items.get_by_id(cmd.source_item_id),
                SourceItemNotFoundError,
                f"Source item #{cmd.source_item_id} not found.",
            )
            SourceItemCatalogueRules.assert_item_demandable(source_item)

        if cmd.made_item_id is not None:
            made_item = found_or_raise(
                await self._made_items.get_by_id(cmd.made_item_id),
                MadeItemNotFoundError,
                f"Made item #{cmd.made_item_id} not found.",
            )
            MadeItemCatalogueRules.assert_item_demandable(made_item)

    async def _reset_source_approval(
        self, lot: ProductionLot, cmd: SwitchLotMaterialSourceCommand
    ) -> MaterialSupply:
        """A new source is a new approval decision. It is derived from
        scratch and every decision field is cleared, because an old approval
        or rejection was about the old source (see this module's
        docstring). Returns who brings the material of the lot's first
        position, which the lot names its new source for already."""
        settings = await self._settings.get_production()
        supply = lot_supply(lot, enabled=settings.external_first_step_needs_no_material)
        lot.source_approval_status = (
            initial_status(
                supply,
                approval_required=settings.require_source_item_approval,
                source_is_item=cmd.source_item_id is not None,
            )
            if cmd.bought_item_id is not None or cmd.source_item_id is not None
            else SourceApprovalStatus.NOT_REQUIRED
        )
        lot.source_approved_by_id = None
        lot.source_approved_date = None
        lot.source_rejected_by_id = None
        lot.source_rejected_date = None
        lot.source_rejection_reason = None
        return supply

    async def _create_source_item_demand(
        self,
        actor: User,
        lot: ProductionLot,
        now: datetime,
        missing: tuple[float, str, float] | None,
        supply: MaterialSupply,
    ) -> None:
        """The new source's demand: the whole lot, or with `missing` what the
        replaced demand still lacked, in its unit, never more than a MIXED
        first position makes in house."""
        quantity, unit, items_per_unit = missing or (lot.quantity, "pcs", 1.0)
        quantity = capped_to_in_house(lot, supply, quantity)
        if not quantity_gt(quantity, 0.0):
            return
        demand = build_source_item_demand(
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
        saved_demand = await self._demands.save(demand)
        self._reconciler.touch_demands(
            LifecycleAggregate.SOURCE_DEMANDS, [saved_demand.id], created=True
        )
        lot.input_demand_id = saved_demand.id
        lot.changes = append_changelog(
            lot.changes, actor.full_name, f"Linked source item demand #{saved_demand.id}."
        )
