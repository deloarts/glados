"""
The other half of ApproveLotSource: records a sticky, visible rejection
(reason required and length-capped, see RejectLotSourceRequest's
field_validator) instead of creating a demand. Unlike approve, reject only
ever fires from `pending`; there is no "reject an already-rejected lot"
or "reject an already-approved one" (the latter would silently orphan a
live demand outside CancelLot/SwitchLotMaterialSource's own bookkeeping,
neither of which this use case owns). Two ways out of `rejected`: the
planner switches the material source (SwitchLotMaterialSource resets to
pending), or an approver approves after all (ApproveLotSource accepts
`rejected` as a starting state, see that module). A client sends the lot's
edit version it read, and a rejection moves it, so a stale view answers 409
instead of deciding about a source it did not see.
"""

from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import RejectLotSourceCommand
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class RejectLotSource:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        *,
        uow: IUnitOfWork,
        lock_plan: LockPlan | None = None,
    ) -> None:
        self._lots = lot_repo
        self._uow = uow
        self._lock_plan = lock_plan

    async def execute(self, actor: User, lot_id: int, cmd: RejectLotSourceCommand) -> LotResult:
        # Locked before it is read, so the pending check below cannot race an
        # approval or another rejection.
        if self._lock_plan is not None:
            await self._lock_plan.acquire(AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]}))
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )

        LotRules.assert_can_approve_source(actor, lot, LifecycleAction.REJECT_SOURCE)
        assert_edit_version(lot, cmd.expected_edit_version, what=f"Lot #{lot.id}")

        now = now_utc()
        bump_edit_version(lot)
        lot.source_approval_status = SourceApprovalStatus.REJECTED
        lot.source_rejected_by_id = actor.id
        lot.source_rejected_date = now
        lot.source_rejection_reason = cmd.reason
        lot.source_approved_by_id = None
        lot.source_approved_date = None
        lot.changed = now
        lot.changes = append_changelog(
            lot.changes, actor.full_name, f"Material source rejected. Reason: {cmd.reason}"
        )
        saved_lot = await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                saved_lot.id,
                actor,
                LotEventType.LOT_SOURCE_REJECTED,
                "lot",
                f"Material source rejected. Reason: {cmd.reason}",
            )
        )

        await self._uow.commit()
        log.info(f"Rejected the material source for lot {saved_lot.lot_number!r}: {cmd.reason}")
        return LotMapper.to_result(saved_lot)
