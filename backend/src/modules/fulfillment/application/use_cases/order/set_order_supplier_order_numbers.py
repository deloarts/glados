"""
Replaces the supplier order numbers of an order, the numbers under which the
supplier keeps it, with the list the request sends.

The numbers are not lifecycle facts: they change no status, so the use case
runs no reconciler. It locks the order, which serializes it with every other
order writer, and moves the order's edit version, since the numbers are part
of what the user edits. They arrive with the supplier's confirmations, after
the order went out, so they need only write:orders in every status until the
order is delivered or canceled (the order intent table's
edit_supplier_order_numbers rule).
"""

from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.order_dto import SetOrderSupplierOrderNumbersCommand
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.services.supplier_order_numbers import (
    normalized_supplier_order_numbers,
)
from src.modules.fulfillment.domain.services.supplier_order_numbers import (
    shown_supplier_order_numbers,
)
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
from src.shared_kernel.domain.services.changelog_service import append_field_changes
from src.shared_kernel.domain.services.clock import now_utc

_FIELD = "supplier_order_numbers"


class SetOrderSupplierOrderNumbers:
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
        self, actor: User, order_id: int, cmd: SetOrderSupplierOrderNumbersCommand
    ) -> OrderResult:
        OrderRules.assert_can_write_orders(actor)
        if self._lock_plan is not None:
            await self._lock_plan.acquire(AggregateIds.of({LifecycleAggregate.ORDERS: [order_id]}))
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        OrderRules.assert_can_edit_supplier_order_numbers(actor, order)
        assert_edit_version(order, cmd.expected_edit_version, what=f"Order #{order.id}")

        numbers = normalized_supplier_order_numbers(cmd.numbers)
        if numbers != order.supplier_order_numbers:
            before = {_FIELD: shown_supplier_order_numbers(order.supplier_order_numbers)}
            after = {_FIELD: shown_supplier_order_numbers(numbers)}
            bump_edit_version(order)
            order.supplier_order_numbers = numbers
            order.changed = now_utc()
            order.changes = append_field_changes(order.changes, actor.full_name, before, after)
            await self._orders.save(order)
        await self._uow.commit()

        saved = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        lines = await self._order_items.get_by_order_id(order_id)
        return OrderMapper.to_result(saved, items=lines)
