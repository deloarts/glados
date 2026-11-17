"""
Reopening a line closed short share-locks the line's project before the
lifecycle locks and checks it active under them. A line moved to another
project between that read and the locks is refused as a concurrent change
and stays closed, since the share lock taken is not the one of its project.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.use_cases.order.reopen_order_item import ReopenOrderItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.production_lot.fakes import FakeProjectRepository

MANAGER = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])


class MovedAfterTheFirstRead(FakeOrderItemRepository):
    """Answers the first read of the line with the project it had then and
    every later read with the project it was moved to meanwhile."""

    def __init__(self, line: OrderItem, read_project_id: int) -> None:
        super().__init__([line])
        self._first: OrderItem | None = replace(line, project_id=read_project_id)

    async def get_by_id(self, id: int) -> OrderItem | None:
        if self._first is not None and self._first.id == id:
            first, self._first = self._first, None
            return first
        return await super().get_by_id(id)


def _closed_line(project_id: int) -> OrderItem:
    line = make_order_item(id=1, status=OrderItemStatus.DELIVERED)
    line.project_id = project_id
    line.quantity = 8.0
    line.quantity_delivered = 8.0
    line.closed_short_at = datetime(2026, 3, 1, tzinfo=UTC)
    line.closed_short_from = 10.0
    return line


def _reopen(lines: FakeOrderItemRepository, projects: FakeProjectRepository) -> ReopenOrderItem:
    orders = FakeOrderRepository([make_order(id=1, status=OrderStatus.DELIVERED)])
    return ReopenOrderItem(
        orders,
        lines,
        project_repo=projects,
        uow=FakeUnitOfWork(),
        reconciler=order_reconciler(orders, lines),
    )


async def test_a_line_moved_to_another_project_before_the_locks_is_refused() -> None:
    lines = MovedAfterTheFirstRead(_closed_line(project_id=2), read_project_id=1)
    projects = FakeProjectRepository()

    with pytest.raises(ConcurrentModificationError):
        await _reopen(lines, projects).execute(MANAGER, 1, 1)

    assert projects.share_locked == [[1]]
    line = await lines.get_by_id(1)
    assert line is not None
    assert (line.quantity, line.closed_short_at is not None) == (8.0, True)


async def test_a_line_on_the_project_read_is_reopened_under_its_share_lock() -> None:
    lines = FakeOrderItemRepository([_closed_line(project_id=2)])
    projects = FakeProjectRepository()

    result = await _reopen(lines, projects).execute(MANAGER, 1, 1)

    assert projects.share_locked == [[2]]
    assert (result.quantity, result.closed_short_at) == (10.0, None)
