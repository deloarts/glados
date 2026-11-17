"""
Planner-adjustable fields on an existing ProductionOrder. `priority`,
`pinned`, and `planned_start`/`planned_end` require MANAGE_PRODUCTION_ORDERS,
since these are the priority-override and pin/unpin controls, the
auto-planner never moves pinned orders; `not_before`,
`estimated_duration_minutes`, and `note` only need WRITE_PRODUCTION_ORDERS
(same guard `assert_can_update` already applies, including its pinned-lock
check for orders this actor doesn't have MANAGE rights over).

Setting planned_start/planned_end auto-pins the order unless `pinned` is
explicitly provided in the same request, because a manual schedule
override with nothing pinning it in place would just get silently
reshuffled by a queue reorder or by the auto-planner.

A change of the pin or the planned window takes the order's queue lock
first, the lock Auto-Plan holds for its whole run while it writes the pins
and windows of that queue, so the edit waits for a running Auto-Plan and is
applied on top of its result instead of being overwritten by it. The order
row is then locked through the request's lock plan and read again before the
checks, and an order that moved to another queue in between is refused with
ConcurrentModificationError (queue_scope_locks.py).
"""

from datetime import datetime

from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    UpdateProductionOrderCommand,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.queue_scope_locks import assert_queue_scope_held
from src.modules.fulfillment.application.services.queue_scope_locks import lock_queue_scopes_first
from src.modules.fulfillment.application.services.scheduling_context import holiday_dates
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import place
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc


class UpdateProductionOrder:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        calendar_repo: IMachineCalendarRepository | None = None,
        settings_repo: IFulfillmentSettingsRepository | None = None,
        *,
        uow: IUnitOfWork,
        lock_plan: LockPlan,
    ) -> None:
        self._orders = order_repo
        self._uow = uow
        self._lock_plan = lock_plan
        self._recompute = recompute_schedule
        self._calendars = calendar_repo
        self._settings = settings_repo

    async def execute(
        self, actor: User, production_order_id: int, cmd: UpdateProductionOrderCommand
    ) -> ProductionOrderResult:
        order = await self._load(production_order_id)
        ProductionOrderRules.assert_can_update(actor, order)
        order = await self._lock(order, cmd)
        ProductionOrderRules.assert_can_update(actor, order)
        # A terminal order is done, so block the whole edit (permission check
        # first, so a permission-less caller still 403s before learning state).
        if order.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
            raise ProductionOrderInvalidStatusTransitionError(
                f"Production order #{order.id} is {order.status.value} and can no longer be edited."
            )
        assert_edit_version(order, cmd.expected_edit_version, what=f"Production order #{order.id}")
        if cmd.priority is not None or cmd.pinned is not None or cmd.planned_start is not None:
            ProductionOrderRules.assert_can_manage(actor)
        if cmd.planned_start is not None:
            ProductionOrderRules.assert_can_set_schedule(order)

        changed_fields = []
        if cmd.priority is not None:
            order.priority = cmd.priority
            changed_fields.append(f"priority -> {cmd.priority.value}")
        if cmd.pinned is not None:
            order.pinned = cmd.pinned
            changed_fields.append(f"pinned -> {cmd.pinned}")
        if cmd.not_before is not None:
            order.not_before = cmd.not_before
            changed_fields.append(f"not_before -> {cmd.not_before}")
        if cmd.estimated_duration_minutes is not None:
            order.estimated_duration_minutes = cmd.estimated_duration_minutes
            changed_fields.append(f"estimated_duration_minutes -> {cmd.estimated_duration_minutes}")
        if cmd.note is not None:
            order.note = cmd.note
            changed_fields.append("note updated")
        if cmd.planned_start is not None:
            if cmd.recompute_planned_end:
                planned_start, planned_end = await self._compute_end_from_start(
                    order, cmd.planned_start
                )
            else:
                # The validator guarantees planned_end is set together with
                # planned_start whenever recompute_planned_end is False.
                assert cmd.planned_end is not None
                # A client may send these without an offset; the columns are
                # `timestamptz`, so pin the frame here rather than letting the
                # database read a naive value in its own session timezone.
                planned_start, planned_end = as_utc(cmd.planned_start), as_utc(cmd.planned_end)
            order.planned_start = planned_start
            order.planned_end = planned_end
            order.planned_by_id = actor.id
            changed_fields.append(f"planned_start -> {planned_start}, planned_end -> {planned_end}")
            if cmd.pinned is None:
                order.pinned = True
                changed_fields.append("pinned -> True (auto-pinned by manual schedule)")

        if not changed_fields:
            return ProductionOrderMapper.to_result(order)

        bump_edit_version(order)
        order.changed = now_utc()
        order.changes = append_changelog(
            order.changes, actor.full_name, "Updated: " + ", ".join(changed_fields)
        )
        saved = await self._orders.save(order)
        # Committed before the schedule recompute below, which only reads
        # committed rows.
        await self._uow.commit()
        # After the commit, so the line means "persisted", matching the
        # sibling use cases (production_order_lifecycle.py,
        # split_production_order.py, etc). The no-op early return above
        # stays silent, nothing changed.
        log.info(
            "Updated production order #%s: %s.",
            production_order_id,
            ", ".join(changed_fields),
        )

        # A single execute_all() walk always covers every
        # machine/pool/bucket, including any later
        # position's machine in the same lot, so there's nothing left to
        # opt into separately, unlike when this only walked
        # saved.machine_id's own queue.
        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"updating production order #{production_order_id}; the update itself is committed."
            ),
        )

        return ProductionOrderMapper.to_result(saved)

    async def _load(self, production_order_id: int) -> ProductionOrder:
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        return order

    async def _lock(
        self, order: ProductionOrder, cmd: UpdateProductionOrderCommand
    ) -> ProductionOrder:
        """Takes the order's queue lock when the pin or the window changes,
        then the order's row lock, and returns the order read under them."""
        schedules = cmd.pinned is not None or cmd.planned_start is not None
        scopes = await lock_queue_scopes_first(
            self._orders, [(order.machine_id, order.machine_pool_id)] if schedules else []
        )
        await self._lock_plan.acquire(
            AggregateIds.of({LifecycleAggregate.PRODUCTION_ORDERS: [order.id]})
        )
        locked = await self._load(order.id)
        if schedules:
            assert_queue_scope_held(scopes, locked.machine_id, locked.machine_pool_id, locked.id)
        return locked

    async def _compute_end_from_start(
        self, order: ProductionOrder, start: datetime
    ) -> tuple[datetime, datetime]:
        if order.machine_id is None:
            raise ProductionOrderNoMachineAssignedError(
                f"Production order #{order.id} has no machine assigned - "
                "planned_end can't be computed without a calendar to walk."
            )
        assert self._settings is not None and self._calendars is not None
        settings = await self._settings.get_production()
        working_hours = await self._calendars.get_working_hours_by_machine_id(order.machine_id)
        exceptions = await self._calendars.get_exceptions_by_machine_id(order.machine_id)
        calendar = build_machine_calendar(
            settings.default_weekly_hours,
            working_hours.weekly_hours if working_hours else None,
            {e.exception_date: e.hours for e in exceptions},
            zone=await tenant_zone(self._settings),
            holidays=await holiday_dates(self._calendars),
        )
        return place(start, order.estimated_duration_minutes, calendar)
