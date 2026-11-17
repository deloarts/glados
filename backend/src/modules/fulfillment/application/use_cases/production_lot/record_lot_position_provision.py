"""
Records the physical outbound dispatch of parts to a supplier for an
EXTERNAL LotPosition, optional, informational to purchasing but
hard-capped: provided <= available input from the predecessor position
(reuses lot_rules.available_input, unchanged). "delivered <= provided" is
meant to surface as a warning and, like the existing
lot_rules.warn_out_of_sequence_ordering, is not yet wired into a response
field or blocking check anywhere in this codebase, left for a later pass
alongside that existing warning, not a gap introduced here.
"""

from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionProvisionResult
from src.modules.fulfillment.application.dto.production_lot_dto import (
    RecordLotPositionProvisionCommand,
)
from src.modules.fulfillment.application.mappers.production_lot_mapper import (
    LotPositionProvisionMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionNotAssignableError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionProvisionOverflowError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import PositionRefusal
from src.modules.fulfillment.domain.services.lot_rules import available_input
from src.modules.fulfillment.domain.services.lot_rules import lot_position_context
from src.modules.fulfillment.domain.services.lot_rules import lot_position_refusal
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class RecordLotPositionProvision:
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

    async def execute(
        self,
        actor: User,
        lot_id: int,
        position_id: int,
        cmd: RecordLotPositionProvisionCommand,
    ) -> LotPositionProvisionResult:
        position = await self._lots.get_position_by_id(position_id)
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        # Locked through the request's lock plan, then read: two concurrent
        # provisions against the same lot must not both compute `available`
        # from the same pre-insert existing_total and both pass the overflow
        # check below (see IProductionLotRepository.get_by_id_for_update).
        # Held until the unit of work commits below.
        if self._lock_plan is not None:
            await self._lock_plan.acquire(AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]}))
        lot = found_or_raise(
            await self._lots.get_by_id_for_update(lot_id),
            LotNotFoundError,
            f"Lot #{lot_id} not found.",
        )
        # Recording a provision is a lot mutation, gated exactly like a
        # sibling lot mutation (write:lots, escalating to manage:lots on a
        # terminal lot). The lot is already in hand from the locked read.
        LotRules.assert_can_update(actor, lot)
        # The checks again on the position as the locked lot holds it: an
        # unassign committed meanwhile leaves nothing to provision, and an
        # ended lot takes no provision.
        locked_position = next((p for p in lot.positions if p.id == position_id), None)
        if locked_position is None:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        position = locked_position
        refusal = lot_position_refusal(
            LifecycleAction.RECORD_PROVISION,
            position,
            lot_position_context(position, lot.status),
            actor,
        )
        if refusal is PositionRefusal.LOT_TERMINAL:
            raise LotInvalidStatusTransitionError(
                f"Lot #{lot_id} is {lot.status.value} and takes no provision."
            )
        if refusal is not None:
            raise LotPositionNotAssignableError(
                f"Position #{position_id} is not EXTERNAL/MIXED; provisions only apply to "
                f"positions with a supplier-executed share."
            )

        existing_total = sum(p.quantity for p in await self._lots.get_provisions(position_id))
        # What a MIXED position's own orders processed came from the same
        # input, so it is not there to hand to the supplier.
        in_house = (
            sum((order.pieces_processed for order in position.production_orders), 0.0)
            if position.kind == LotPositionKind.MIXED
            else 0.0
        )
        available = available_input(lot.positions, lot.quantity, position.sequence) - in_house
        if quantity_gt(existing_total + cmd.quantity, available):
            raise LotPositionProvisionOverflowError(
                f"Position #{position_id} has {available:.3f} available from its predecessor "
                f"after the {in_house:.3f} processed in house; cannot provision "
                f"{cmd.quantity:.3f} more (already provisioned {existing_total:.3f})."
            )

        provision = LotPositionProvision(
            id=0,
            lot_position_id=position_id,
            quantity=cmd.quantity,
            provision_date=cmd.provision_date,
            note=cmd.note,
            creator_id=actor.id,
            created=now_utc(),
        )
        saved = await self._lots.save_provision(provision)
        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.POSITION_PROVISION_RECORDED,
                "position",
                f"Provision of {cmd.quantity:.3f} recorded for position #{position_id}.",
                entity_id=position_id,
                payload={"quantity": cmd.quantity, "provision_id": saved.id},
            )
        )
        await self._uow.commit()

        log.info(
            f"Recorded a provision of {cmd.quantity:.3f} for "
            f"position #{position_id} of lot #{lot_id}."
        )
        return LotPositionProvisionMapper.to_result(saved)


class GetLotPositionProvisions:
    def __init__(self, lot_repo: IProductionLotRepository) -> None:
        self._lots = lot_repo

    async def execute(self, lot_id: int, position_id: int) -> list[LotPositionProvisionResult]:
        position = await self._lots.get_position_by_id(position_id)
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        provisions = await self._lots.get_provisions(position_id)
        return [LotPositionProvisionMapper.to_result(p) for p in provisions]
