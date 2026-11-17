"""
Replaces the extra costs of an order, such as shipping, packaging or a
surcharge, with the list the request sends.

Extra costs are not lifecycle facts: they have no status, are never
received and never change what a line or demand derives, so the use case
runs no reconciler. It locks the order, which serializes it with every other
order writer, and moves the order's edit version, since the costs are part
of what the user edits. They follow the order's edit rule, write:orders
while it is a draft or requested and manage:orders after that, and stay
editable once the order is delivered, because shipping is often known only
from the invoice. A canceled order takes no change.
"""

from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.order_dto import SetOrderExtraCostsCommand
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.errors import OrderCanceledError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.extra_cost_rules import ExtraCostDraft
from src.modules.fulfillment.domain.services.extra_cost_rules import assert_valid_extra_costs
from src.modules.fulfillment.domain.services.extra_cost_rules import describe_extra_cost_change
from src.modules.fulfillment.domain.services.extra_cost_rules import normalized_label
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class SetOrderExtraCosts:
    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        lock_plan: LockPlan | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._uow = uow
        self._lock_plan = lock_plan

    async def execute(
        self, actor: User, order_id: int, cmd: SetOrderExtraCostsCommand
    ) -> OrderResult:
        OrderRules.assert_can_write_orders(actor)
        if self._lock_plan is not None:
            await self._lock_plan.acquire(AggregateIds.of({LifecycleAggregate.ORDERS: [order_id]}))
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        OrderRules.assert_can_update(actor, order)
        if order.canceled_at is not None:
            raise OrderCanceledError(f"Order #{order.id} is canceled and takes no extra costs.")
        assert_edit_version(order, cmd.expected_edit_version, what=f"Order #{order.id}")

        lines = await self._order_items.get_by_order_id(order_id)
        drafts = [
            ExtraCostDraft(
                kind=c.kind,
                amount=c.amount,
                label=normalized_label(c.label),
                note=(c.note or "").strip() or None,
                line_id=c.order_item_id,
            )
            for c in cmd.costs
        ]
        assert_valid_extra_costs(drafts, {line.id for line in lines})
        before = list(order.extra_costs)
        costs = [
            OrderExtraCost(
                id=0,
                order_id=order.id,
                kind=d.kind,
                amount=d.amount,
                position=position,
                label=d.label,
                note=d.note,
                order_item_id=d.line_id,
            )
            for position, d in enumerate(drafts, start=1)
        ]
        change = describe_extra_cost_change(
            [(c.kind, c.amount, c.label, c.note, c.order_item_id) for c in before],
            [(c.kind, c.amount, c.label, c.note, c.order_item_id) for c in costs],
        )
        if change is not None:
            bump_edit_version(order)
            order.changed = now_utc()
            order.changes = append_changelog(order.changes, actor.full_name, change)
            await self._orders.save(order)
            await self._orders.set_extra_costs(order.id, costs)
        await self._uow.commit()

        saved = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        return OrderMapper.to_result(saved, items=lines)
