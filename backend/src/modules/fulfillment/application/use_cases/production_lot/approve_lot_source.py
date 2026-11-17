"""Releases a lot's material source once it has been sitting `pending` (or
overturns a prior `rejected`), letting its raw material enter the
procurement pipeline. Approve is the ONLY place that calls
build_source_item_demand for a source-item-sourced lot while
AdminProductionSettings.require_source_item_approval is on. Approval is not
a second "configure the demand" step, it is a release of the demand
CreateLot or SwitchLotMaterialSource would already have created had approval
not been required, with the same defaults (the three flags false/None). A
lot nothing of whose material arrived yet is demanded whole (quantity=lot.
quantity, unit="pcs", items_per_unit=1.0). A lot that switched away from an
ordered source kept what arrived there, on the old demand the switch marked
fulfilled, so only the rest is demanded, in that demand's unit, as the
switch itself demands it without approval; with nothing left, no demand is
created.

The demand it creates is new work, so the lot's project must be active and
the source item one that new work may still name; otherwise the planner
switches the source first. The project is share-locked before the lifecycle
locks, as every writer of new work for a project takes it. A client sends
the lot's edit version it read, so an approval from a stale view of a lot
whose source was switched or decided since answers 409.
"""

from src.modules.catalogue.application.facade.made_item_material_source import (
    MadeItemMaterialSources,
)
from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.catalogue_item_status import demandable_refusal
from src.modules.catalogue.domain.policies.material_source_rules import (
    resolve_made_item_source_assignment,
)
from src.modules.catalogue.domain.value_objects.made_item_source_assignment import (
    MadeItemSourceAssignment,
)
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.source_item_demand_factory import (
    build_source_item_demand,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotRawMaterialAlreadyLinkedError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
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
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
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


class ApproveLotSource:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        project_repo: IProjectQueries,
        source_item_repo: ISourceItemQueries,
        # Both None only for pre-existing unit tests constructing this use
        # case without them: production wiring always supplies both (see
        # deps/lots.py). When either is missing the material write-back
        # below is unconditionally skipped (SKIPPED_DISABLED), never
        # attempted half-wired.
        made_items: MadeItemMaterialSources | None = None,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        self._lots = lot_repo
        self._demands = source_item_demand_repo
        self._allocations = source_item_allocation_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._projects = project_repo
        self._made_items = made_items
        self._source_items = source_item_repo
        self._settings = settings_repo

    async def execute(
        self, actor: User, lot_id: int, *, expected_edit_version: int | None = None
    ) -> LotResult:
        # A lot never changes project, so the project read here is the one
        # the locked lot carries.
        read = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        await self._projects.lock_for_share([read.project_id])
        # Locked through the request's lock plan before it is read, so two
        # approvals, or an approval and a rejection, serialize on the lot and
        # the second one sees the first one's result.
        await self._reconciler.lock_touched(
            also=AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]})
        )
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )

        LotRules.assert_can_approve_source(actor, lot, LifecycleAction.APPROVE_SOURCE)
        assert_edit_version(lot, expected_edit_version, what=f"Lot #{lot.id}")
        # Race backstop: two approvers submitting at once could both pass
        # the status check above before either commits. A second demand
        # insert for the same lot would hit the partial unique index
        # uq_source_item_demand_lot_id_active and surface as a raw
        # IntegrityError (500) rather than a clean 409; this turns that
        # race into the same error CreateSourceItemDemand's own
        # one-shot-per-lot guard raises.
        if lot.input_demand_id is not None:
            raise LotRawMaterialAlreadyLinkedError(
                f"Lot #{lot_id} already has a linked source item demand (#{lot.input_demand_id})."
            )

        await self._assert_new_work_allowed(lot)

        now = now_utc()
        bump_edit_version(lot)
        lot.source_approval_status = SourceApprovalStatus.APPROVED
        lot.source_approved_by_id = actor.id
        lot.source_approved_date = now
        lot.source_rejected_by_id = None
        lot.source_rejected_date = None
        lot.source_rejection_reason = None
        lot.changed = now
        lot.changes = append_changelog(lot.changes, actor.full_name, "Material source approved.")

        # Optional write-back: assign the just-approved source item onto
        # the lot's made item, gated on manage:lots alone (no
        # write:made_items check required) and never allowed to fail the
        # approval itself. assignment stays
        # SKIPPED_DISABLED whenever any of the three repos is missing
        # (pre-existing unit tests) or the setting is off.
        assignment = MadeItemSourceAssignment.SKIPPED_DISABLED
        made_item = None
        write_back_wired = self._made_items is not None and self._settings is not None
        if write_back_wired:
            assert self._made_items is not None
            assert self._settings is not None
            settings = await self._settings.get_production()
            if settings.assign_approved_material_to_item:
                made_item = await self._made_items.get_by_id(lot.made_item_id)
                source_item = (
                    await self._source_items.get_by_id(lot.source_item_id)
                    if lot.source_item_id is not None
                    else None
                )
                assignment = resolve_made_item_source_assignment(
                    assign_enabled=settings.assign_approved_material_to_item,
                    overwrite_enabled=settings.overwrite_item_material_on_approval,
                    lot_source_item_id=lot.source_item_id,
                    made_item_bought_item_id=made_item.bought_item_id if made_item else None,
                    made_item_source_item_id=made_item.source_item_id if made_item else None,
                    source_item_is_active=(
                        source_item is not None
                        and source_item.status == SourceItemCatalogueStatus.ACTIVE.value
                    ),
                    made_item_found=made_item is not None,
                )

        if assignment == MadeItemSourceAssignment.ASSIGNED:
            assert made_item is not None
            assert self._made_items is not None
            assert lot.source_item_id is not None
            await self._made_items.assign_source_item(
                made_item,
                lot.source_item_id,
                actor,
                f"Material source set to source item #{lot.source_item_id} on approval of lot "
                f"{lot.lot_number!r}.",
            )
            lot.changes = append_changelog(
                lot.changes,
                actor.full_name,
                f"Assigned approved material to made item #{lot.made_item_id}.",
            )
        elif assignment != MadeItemSourceAssignment.SKIPPED_DISABLED:
            lot.changes = append_changelog(
                lot.changes,
                actor.full_name,
                f"Made item #{lot.made_item_id} not updated ({assignment.value}).",
            )

        quantity, unit, items_per_unit = await self._missing_material(lot)
        saved_demand = None
        if quantity_gt(quantity, 0.0):
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
        demand_id = saved_demand.id if saved_demand is not None else None

        saved_lot = await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                saved_lot.id,
                actor,
                LotEventType.LOT_SOURCE_APPROVED,
                "lot",
                "Material source approved.",
                payload={
                    "source_item_demand_id": demand_id,
                    "made_item_id": lot.made_item_id,
                    "made_item_source_assignment": assignment.value,
                },
            )
        )

        await self._reconciler.run(actor, now)
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"approving the material source for "
                f"lot #{lot_id}; the approval itself is committed."
            ),
        )

        log.info(
            f"Approved the material source for lot "
            f"{saved_lot.lot_number!r}, created source item demand #{demand_id} "
            f"(made item source assignment: {assignment.value})."
        )
        result_lot = await self._lots.get_by_id(lot_id)
        assert result_lot is not None
        return LotMapper.to_result(result_lot)

    async def _missing_material(self, lot: ProductionLot) -> tuple[float, str, float]:
        """What the approved source still has to bring, as (quantity, unit,
        items per unit). The lot's latest demand that was not canceled is the
        one a source switch settled at what arrived, whose allocations the
        switch cut down to those pieces, so the rest of it is what is
        missing. Without one, nothing arrived yet and the whole lot is."""
        _, latest = await self._demands.get_multi(
            SourceItemDemandFilterDto(
                lot_id=[lot.id], ignore_canceled=True, order_by="id", order_dir="desc", limit=1
            )
        )
        if not latest:
            return (lot.quantity, "pcs", 1.0)
        settled = latest[0]
        arrived = sum(a.quantity for a in await self._allocations.get_by_demand_item_id(settled.id))
        return (max(settled.quantity - arrived, 0.0), settled.unit, settled.items_per_unit)

    async def _assert_new_work_allowed(self, lot: ProductionLot) -> None:
        """The demand an approval creates is new work: the lot's project must
        be active and its source item one new work may still name."""
        assert_project_active(
            found_or_raise(
                await self._projects.get_by_id(lot.project_id),
                ProjectNotFoundError,
                f"Project #{lot.project_id} not found.",
            ),
            work="approved material sources",
        )
        if lot.source_item_id is None:
            return
        source_item = found_or_raise(
            await self._source_items.get_by_id(lot.source_item_id),
            SourceItemNotFoundError,
            f"Source item #{lot.source_item_id} not found.",
        )
        reason = demandable_refusal(status=source_item.status, archived=source_item.archived)
        if reason is not None:
            raise SourceItemInactiveError(
                f"Source item #{source_item.id} {reason}, so lot #{lot.id}'s material source "
                "cannot be approved; switch the source first."
            )
