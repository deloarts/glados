"""
Reopens an order line closed short, when the supplier sends the rest after
all or a closed line needs a delivery correction: the line's quantity goes
back to what it was before the close, the close is cleared, and the line
derives PARTIALLY_DELIVERED again while pieces are open. The allocations the
close fitted stay as they are, since the demands' rest may be allocated
elsewhere by now; the line's capacity is free for new allocations. The
lifecycle reconciler derives the statuses of the line and its order.

Only a delivered line closed short is reopened, never a MADE line, which its
lot closed, nor a line of a canceled order. A line closed short before the
close was recorded has no quantity to go back to and is refused as not
closed short. Like the close it undoes, a reopen checks the line's edit
version the client read under the line's lock. A reopened line is new work
for its project, so the project must be active; reactivating it comes first.
The project is share-locked before the lifecycle locks, so a line moved to
another project in between is refused as a concurrent change.
"""

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order._lines import read_order_line
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# Closes the changelog lines of the statuses a reopen moves.
_REOPENED = "reopened"


class ReopenOrderItem:
    """Reopens one line of an order closed short; see the module docstring.
    Needs the order's update permission."""

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        *,
        project_repo: IProjectQueries,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._projects = project_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self,
        actor: User,
        order_id: int,
        order_item_id: int,
        *,
        expected_edit_version: int | None = None,
    ) -> OrderItemResult:
        _, found = await read_order_line(self._orders, self._order_items, order_id, order_item_id)
        # Shared, before the lifecycle locks, as every writer of new work for
        # a project takes it (IProjectQueries.lock_for_share).
        await self._projects.lock_for_share([found.project_id])
        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched()
        order, item = await read_order_line(
            self._orders, self._order_items, order_id, order_item_id
        )
        OrderRules.assert_can_reopen(actor, order, item)
        assert_edit_version(item, expected_edit_version, what=f"Order item #{item.id}")
        if item.project_id != found.project_id:
            # Moved to another project between the read and the locks, so the
            # share lock taken is not the one of the line's project.
            raise ConcurrentModificationError(
                f"Order item #{item.id} was moved to another project since it was read; "
                "reload it and try again."
            )
        assert_project_active(
            found_or_raise(
                await self._projects.get_by_id(item.project_id),
                ProjectNotFoundError,
                f"Project #{item.project_id} not found.",
            ),
            work="reopened order lines",
        )

        now = now_utc()
        closed_quantity = item.quantity
        bump_edit_version(item)
        item.quantity = item.closed_short_from or item.quantity
        item.closed_short_at = None
        item.closed_short_from = None
        item.changed = now
        item.changes = append_changelog(
            item.changes,
            actor.full_name,
            f"Reopened: quantity back to {item.quantity:.3f} from {closed_quantity:.3f} "
            f"{item.unit}.",
        )
        await self._order_items.save(item)

        await self._reconciler.run(actor, now, reason=_REOPENED)
        await self._uow.commit()

        log.info(f"Reopened order item #{order_item_id} of order #{order_id}.")
        reopened = await self._order_items.get_by_id(order_item_id)
        return OrderItemMapper.to_result(reopened or item)
