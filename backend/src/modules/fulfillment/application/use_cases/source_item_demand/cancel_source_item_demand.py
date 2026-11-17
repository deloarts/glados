"""
Canceling records the demand's canceled_at, releases every allocation it
holds, on order lines and from stock, and frees the lot to demand its source
item again (nulls ProductionLot.input_demand_id). It is blocked once the
demand is fulfilled, since that would silently orphan a completed
procurement, and once the lot has started production, since the lot would
then wait on material it already holds; its source is switched or the lot
force-completed instead. The lifecycle reconciler derives CANCELED and
publishes the status event.

While the demand is the raw material demand of a lot that has not ended, the
caller says what becomes of the lot. `cancel_lot=True` cancels the lot
through CancelLot, whose cascade settles the demand with it, in one
transaction and with the lot's own cancel permission. `cancel_lot=False`
cancels only the demand, and the lot waits on raw material until its source
is switched. Without the choice the cancel is refused (422), so no client
leaves a lot without material by accident. For any other demand the choice
is not needed and a True is ignored, since there is no lot left to cancel.

`execute` serves the cancel route and needs the lot's update permission.
`execute_permitted` serves the status route, whose caller has already
applied the rule all three demand families share, so both routes cancel the
same way.
"""

from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.application.services.allocation_release import release_source_demand
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import CANCEL_REASON
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import SourceItemDemandLotChoiceRequiredError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.services.demand_status_rules import assert_demand_intent
from src.modules.fulfillment.domain.services.lifecycle.lot import lot_has_started
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
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
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def assert_source_demand_cancelable(
    actor: User, demand: SourceItemDemandItem, lot: ProductionLot | None
) -> None:
    """Raises unless the demand intent table lets the source demand be
    canceled now: a fulfilled or canceled one is refused (409), and so is
    the demand of a lot that has started production (409)."""
    assert_demand_intent(
        actor,
        LifecycleAction.CANCEL,
        demand,
        has_allocations=False,
        already_fulfilled_error=SourceItemDemandAlreadyFulfilledError,
        already_canceled_error=SourceItemDemandAlreadyCanceledError,
        noun="Source item demand",
        lot_started=lot is not None and lot_has_started([p.status for p in lot.positions]),
    )


def feeds_live_lot(demand: SourceItemDemandItem, lot: ProductionLot | None) -> bool:
    """Whether the demand is the raw material demand of a lot that has not
    ended, the case in which a cancel needs the caller's choice for the lot."""
    return (
        lot is not None
        and lot.input_demand_id == demand.id
        and lot.status not in TERMINAL_LOT_STATUSES
    )


class CancelSourceItemDemand:
    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        lot_repo: IProductionLotRepository,
        allocation_repo: ISourceItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        cancel_lot: CancelLot,
    ) -> None:
        self._demands = demand_repo
        self._lots = lot_repo
        self._allocations = allocation_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._cancel_lot = cancel_lot

    async def execute(
        self, actor: User, demand_id: int, *, cancel_lot: bool | None = None
    ) -> SourceItemDemandResult:
        demand = await self._read(demand_id)

        # The permission is checked before the intent, which execute_permitted
        # checks under the lock. Fail-closed: a dangling lot_id must not skip
        # the permission check entirely, it falls back to a bare write:lots
        # requirement instead.
        lot = await self._lots.get_by_id(demand.lot_id)
        if lot:
            LotRules.assert_can_update(actor, lot)
        else:
            assert_has_permission(actor, Permission.WRITE_LOTS, "cancel", "source item demands")
        return await self.execute_permitted(actor, demand_id, cancel_lot=cancel_lot)

    async def execute_permitted(
        self, actor: User, demand_id: int, /, *, cancel_lot: bool | None = None
    ) -> SourceItemDemandResult:
        """The cancel for a caller that has already decided the actor may
        cancel the demand. Canceling the lot too still needs the lot's own
        cancel permission."""
        demand = await self._read(demand_id)
        if cancel_lot:
            lot = await self._lots.get_by_id(demand.lot_id)
            if feeds_live_lot(demand, lot):
                assert lot is not None
                return await self._cancel_with_lot(actor, demand, lot)
        # The lot, whose link is cleared, sorts before the demand in the
        # lock order; both are locked before anything is checked.
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand_id])
        await self._reconciler.lock_touched(
            also=AggregateIds.of({LifecycleAggregate.LOTS: [demand.lot_id]})
        )
        demand = await self._read(demand_id)
        lot = await self._lots.get_by_id(demand.lot_id)
        assert_source_demand_cancelable(actor, demand, lot)
        if cancel_lot is None and feeds_live_lot(demand, lot):
            assert lot is not None
            raise SourceItemDemandLotChoiceRequiredError(
                f"Source item demand #{demand_id} is the raw material of lot "
                f"{lot.lot_number!r}. Say whether the lot is canceled too (cancel_lot=true) or "
                f"keeps waiting on raw material until its source is switched (cancel_lot=false)."
            )

        now = now_utc()
        released = await release_source_demand(
            demand, self._allocations, actor, now, "Demand canceled."
        )
        saved = await self._demands.save(demand)

        if lot and lot.input_demand_id == demand.id:
            lot.input_demand_id = None
            lot.changed = now
            lot.changes = append_changelog(
                lot.changes,
                actor.full_name,
                f"Source item demand #{demand.id} canceled and unlinked.",
            )
            await self._lots.save(lot)

        await self._reconciler.run(actor, now, reason=CANCEL_REASON)
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"canceling source item demand #{demand_id}; the cancellation itself is committed."
            ),
        )

        log.info(f"Canceled source item demand #{saved.id}, released {released} allocation(s).")
        canceled = await self._demands.get_by_id(demand_id)
        return SourceItemDemandMapper.to_result(canceled or saved)

    async def _cancel_with_lot(
        self, actor: User, demand: SourceItemDemandItem, lot: ProductionLot
    ) -> SourceItemDemandResult:
        """Cancels the lot the demand feeds, whose cascade settles the
        demand. The demand's own refusals are checked first on the plain read
        and again once CancelLot holds the lot and the demand."""
        assert_source_demand_cancelable(actor, demand, lot)

        async def still_cancelable(locked_lot: ProductionLot) -> None:
            current = await self._read(demand.id)
            assert_source_demand_cancelable(actor, current, locked_lot)
            if not feeds_live_lot(current, locked_lot):
                raise ConcurrentModificationError(
                    f"Lot {locked_lot.lot_number!r} no longer waits on source item demand "
                    f"#{demand.id}; reload it and try again."
                )

        await self._cancel_lot.execute(
            actor,
            lot.id,
            CancelLotCommand(reason=f"Raw material demand #{demand.id} canceled with the lot."),
            under_lock=still_cancelable,
        )
        log.info(f"Canceled source item demand #{demand.id} with lot {lot.lot_number!r}.")
        return SourceItemDemandMapper.to_result(await self._read(demand.id))

    async def _read(self, demand_id: int) -> SourceItemDemandItem:
        return found_or_raise(
            await self._demands.get_by_id(demand_id),
            SourceItemDemandNotFoundError,
            f"Source item demand #{demand_id} not found.",
        )
