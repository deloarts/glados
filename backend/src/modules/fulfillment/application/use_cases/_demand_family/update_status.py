"""
Sets the status of a bought, made or source item demand by hand. Only the
two intents of a demand can be set: `fulfilled`, which records
fulfilled_manually_at, and `canceled`, which is handed to the family's
cancel use case so that both routes cancel the same way; for a made demand
that is the cascade that takes its lots down with it. OPEN, ALLOCATED and
ORDERED follow from the allocations and are refused. The lifecycle
reconciler derives the status and publishes its event.

A bought or source item demand marked fulfilled keeps on each order line only
the pieces that already reached it and releases the rest of its allocations
there (unarrived_release.py), so the lines it held are free to be shrunk or
allocated again. Those lines are locked with the demand. A made item demand
is allocated on lots, which a manual fulfil leaves as they are.

Who may change the status at all is decided by assert_can_change_demand_status,
the rule all three families share, before the requested status is parsed,
so an invalid status from an unauthorized caller still gets 403, and before
the cancel is handed over, so a cancel is gated here whatever the family's
cancel route checks itself. The cancel is therefore reached through its
`execute_permitted`, which applies no permission of its own.

Each family's use case is a subclass in its own package that binds `_spec`,
so the class names that endpoints, deps and tests use stay as they are.
"""

from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.services.allocation_locks import lock_for_allocation
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import FULFIL_REASON
from src.modules.fulfillment.application.use_cases._demand_family.spec import D
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import R
from src.modules.fulfillment.application.use_cases._demand_family.unarrived_release import (
    UnarrivedLineRelease,
)
from src.modules.fulfillment.domain.services.demand_status_rules import (
    assert_can_change_demand_status,
)
from src.modules.fulfillment.domain.services.demand_status_rules import assert_demand_intent
from src.modules.fulfillment.domain.services.demand_status_rules import manual_demand_action
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

R_co = TypeVar("R_co", covariant=True)


class PermittedDemandCancel(Protocol[R_co]):
    """A family's cancel use case, entered by a caller that has already
    decided the actor may cancel the demand."""

    async def execute_permitted(self, actor: User, demand_id: int, /) -> R_co: ...


class UpdateDemandStatus(Generic[D, R]):
    _spec: DemandFamilySpec[D, R]

    def __init__(
        self,
        demand_repo: DemandRepo[D],
        cancel_use_case: PermittedDemandCancel[R],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        line_release: UnarrivedLineRelease[Any] | None,
    ) -> None:
        """`line_release` is the family's release of unarrived line
        allocations, None for the made item family, which has none."""
        self._demands = demand_repo
        self._cancel = cancel_use_case
        self._uow = uow
        self._reconciler = reconciler
        self._line_release = line_release

    async def _hand_over_cancel(self, actor: User, demand_id: int, cancel_lot: bool | None) -> R:
        """Hands the cancel to the family's cancel use case."""
        return await self._cancel.execute_permitted(actor, demand_id)

    async def execute(
        self, actor: User, demand_id: int, new_status: str, *, cancel_lot: bool | None = None
    ) -> R:
        """`cancel_lot` is the caller's choice for the lot a source item
        demand feeds (cancel_source_item_demand.py); the other families have
        no such lot and ignore it."""
        spec = self._spec
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            spec.terms.not_found_error,
            spec.not_found_message(demand_id),
        )

        assert_can_change_demand_status(actor, demand, new_status)
        action = manual_demand_action(demand_id, new_status)

        if demand.status == new_status:
            return spec.to_result(demand)
        if action is LifecycleAction.CANCEL:
            return await self._hand_over_cancel(actor, demand_id, cancel_lot)

        line_ids = await self._held_lines(demand_id)
        await lock_for_allocation(
            self._reconciler, spec.aggregate, [demand_id], order_item_ids=sorted(line_ids)
        )
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            spec.terms.not_found_error,
            spec.not_found_message(demand_id),
        )
        # Compared again under the lock: a demand fulfilled since the first
        # read answers as it does when it already was.
        if demand.status == new_status:
            return spec.to_result(demand)
        assert_demand_intent(
            actor,
            LifecycleAction.FULFIL,
            demand,
            has_allocations=False,
            already_fulfilled_error=spec.terms.already_fulfilled_error,
            already_canceled_error=spec.terms.already_canceled_error,
            noun=spec.terms.noun,
        )

        if not await self._held_lines(demand_id) <= line_ids:
            # An allocation on another line was written between the read and
            # the locks, so that line is not locked.
            raise ConcurrentModificationError(
                f"{spec.terms.noun} #{demand_id} was allocated on another order line since it "
                "was read; reload it and try again."
            )
        released = (
            await self._line_release.release(spec.fill_rank, demand_id)
            if self._line_release is not None
            else 0.0
        )

        now = now_utc()
        demand.fulfilled_manually_at = now
        demand.changed = now
        note = "Marked fulfilled."
        if released:
            note = (
                f"Marked fulfilled; released {released:.3f} {demand.unit} allocated on order "
                "lines that had not arrived."
            )
        demand.changes = append_changelog(demand.changes, actor.full_name, note)
        await self._demands.save(demand)
        await self._reconciler.run(actor, now, reason=FULFIL_REASON)
        await self._uow.commit()

        log.info(f"Marked {spec.log_noun} #%s fulfilled.", demand_id)
        fulfilled = await self._demands.get_by_id(demand_id)
        return spec.to_result(fulfilled or demand)

    async def _held_lines(self, demand_id: int) -> set[int]:
        if self._line_release is None:
            return set()
        return await self._line_release.line_ids(demand_id)
