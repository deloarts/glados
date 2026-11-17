"""
Edits a bought or made item demand: its quantity, unit, items per unit,
priority, delivery notification, note and desired delivery date, plus
whatever fields the family adds, each change noted on the demand's
changelog.

A fulfilled or canceled demand is closed, so nobody may edit it, managers
included. The quantity never drops below what the demand's allocations and
stock already cover, and the lifecycle reconciler derives the demand's
status again, since a smaller quantity can already be fully covered. The
demand is locked as the allocation writers lock it, so the quantity guard
sees every committed allocation.

A family's subclass binds `_spec` and `_demand_rules` and supplies the
checks and fields it adds as hooks.
"""

from datetime import date
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.services.allocation_locks import lock_for_allocation
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import CD
from src.modules.fulfillment.application.use_cases._demand_family.spec import QUANTITY_REASON
from src.modules.fulfillment.application.use_cases._demand_family.spec import CatalogueDemandRules
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import R
from src.modules.fulfillment.domain.services.quantity_edit_rules import (
    assert_demand_quantity_allowed,
)
from src.modules.fulfillment.domain.services.quantity_edit_rules import quantity_changed
from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class AllocatedQuantityRepo(Protocol):
    async def get_allocated_quantity(self, demand_item_id: int, /) -> float: ...


class EditCommand(Protocol):
    """The fields every family's edit form sends."""

    @property
    def quantity(self) -> float: ...

    @property
    def unit(self) -> str: ...

    @property
    def items_per_unit(self) -> float: ...

    @property
    def high_priority(self) -> bool: ...

    @property
    def notify_on_delivery(self) -> bool: ...

    @property
    def note(self) -> str | None: ...

    @property
    def desired_delivery_date(self) -> date | None: ...

    def model_dump(self) -> dict[str, Any]: ...


C = TypeVar("C", bound=EditCommand)


class UpdateDemand(Generic[CD, C, R]):
    _spec: DemandFamilySpec[CD, R]
    _demand_rules: CatalogueDemandRules[CD]

    def __init__(
        self,
        demand_repo: DemandRepo[CD],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        allocation_repo: AllocatedQuantityRepo | None = None,
    ) -> None:
        self._demands = demand_repo
        self._uow = uow
        self._reconciler = reconciler
        self._allocations = allocation_repo

    async def execute(self, actor: User, demand_id: int, cmd: C) -> R:
        spec = self._spec
        await lock_for_allocation(self._reconciler, spec.aggregate, [demand_id])
        demand = found_or_raise(
            await self._demands.get_by_id_for_update(demand_id),
            spec.terms.not_found_error,
            spec.not_found_message(demand_id),
        )

        self._demand_rules.assert_can_update(actor, demand)
        spec.rules.assert_not_terminal(demand)
        self._demand_rules.assert_valid_quantity(cmd.quantity)
        if quantity_changed(demand.quantity, cmd.quantity) or demand.unit != cmd.unit:
            assert_whole_pieces(cmd.quantity, what="The demand quantity", unit=cmd.unit)
        await self._check(demand, cmd)

        if quantity_changed(demand.quantity, cmd.quantity) and self._allocations is not None:
            assert_demand_quantity_allowed(
                demand,
                cmd.quantity,
                await self._allocations.get_allocated_quantity(demand.id),
                noun=spec.terms.noun,
            )

        changelog_entry = diff_command(demand, cmd)

        demand.quantity = cmd.quantity
        demand.unit = cmd.unit
        demand.items_per_unit = cmd.items_per_unit
        demand.high_priority = cmd.high_priority
        demand.notify_on_delivery = cmd.notify_on_delivery
        demand.note = cmd.note
        demand.desired_delivery_date = cmd.desired_delivery_date
        self._apply_extra(demand, cmd)
        demand.changed = now_utc()
        demand.changes = append_changelog(demand.changes, actor.full_name, changelog_entry)

        saved = await self._demands.save(demand)
        self._reconciler.touch_demands(spec.aggregate, [saved.id])
        result = await self._reconciler.run(actor, now_utc(), reason=QUANTITY_REASON)
        if result.changed_ids(spec.aggregate):
            saved = await self._demands.get_by_id(saved.id) or saved
        await self._uow.commit()
        log.info("Updated demand #%s.", saved.id)
        return spec.to_result(saved)

    async def _check(self, demand: CD, cmd: C) -> None:
        """The family's own checks of the edit, run after the shared ones;
        nothing by default."""

    def _apply_extra(self, demand: CD, cmd: C) -> None:
        """Writes the fields the family adds to the edit; nothing by default."""
