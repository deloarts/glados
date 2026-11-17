"""
Notification context links (demand_item_id/order_id/project_id/product_id) are exclusive: at most
one may be set, each names a different deep-link target. An assertion,
not a DB CHECK, since a violation degrades a UI deep-link rather than
corrupting data (see the domain entity's own comment).
"""

import pytest

from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.notification_type import NotificationType


def _make(**context: int | None) -> None:
    make_notification(
        user_id=1,
        type=NotificationType.ORDER_CANCELED,
        title="Title",
        message="Message",
        **context,
    )


class TestSingleContextLinkAccepted:
    def test_demand_item_id_alone(self):
        _make(demand_item_id=1)

    def test_order_id_alone(self):
        _make(order_id=1)

    def test_project_id_alone(self):
        _make(project_id=1)

    def test_product_id_alone(self):
        _make(product_id=1)

    def test_no_context_link_is_valid(self):
        """A context-free notification (e.g. FORCED_LOGOUT) is legitimate,
        not every notification deep-links anywhere."""
        _make()


class TestMultipleContextLinksRejected:
    def test_demand_item_and_order_together_raises(self):
        with pytest.raises(AssertionError, match="demand_item_id"):
            _make(demand_item_id=1, order_id=2)

    def test_all_four_together_raises(self):
        with pytest.raises(AssertionError, match="exclusive"):
            _make(demand_item_id=1, order_id=2, project_id=3, product_id=4)
