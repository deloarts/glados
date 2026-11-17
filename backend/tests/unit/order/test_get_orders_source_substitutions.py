"""
Unit tests for the demand substitutions GetOrders builds for source item
order lines, which follow the same rules as those of bought lines. No
database, no HTTP; every dependency is an in-memory fake.
"""

from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeOrderItemDeliveryRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeSourceItemAllocationRepository
from tests.unit.order._helpers import FakeSourceItemDemandRepository
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_bought_item
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_source_item
from tests.unit.order._helpers import make_source_item_allocation
from tests.unit.order._helpers import make_source_item_demand


class TestGetOrdersSourceSubstitutions:
    """GetOrders takes source_allocation_repo / source_demand_repo so it can
    build demand_substitutions for SOURCE order lines the same way it does
    for BOUGHT lines (_build_substitutions)."""

    def setup_method(self):
        self.order = make_order(id=1)
        self.order_repo = FakeOrderRepository([self.order])

        # The order line itself IS the substitute material (source_item_id=2),
        # the demand's own material is source_item_id=1. This mirrors how a
        # real substituting allocation is built (order_item.source_item_id !=
        # demand.source_item_id).
        self.source_line = make_order_item(id=1, order_id=1, source_item_id=2)
        self.order_items = FakeOrderItemRepository([self.source_line])

        self.original_source_item = make_source_item(
            id=1, dimension="20x20x1000", order_code_1="SRC-OC-1"
        )
        self.demand = make_source_item_demand(
            id=1, source_item_id=1, source_item=self.original_source_item
        )
        self.source_demand_repo = FakeSourceItemDemandRepository([self.demand])

        self.source_allocation = make_source_item_allocation(
            demand_item_id=1,
            order_item_id=1,
            quantity=4.0,
            substitute_source_item_id=2,
            substitute_reason="preferred supplier out of stock",
        )
        self.source_allocation_repo = FakeSourceItemAllocationRepository([self.source_allocation])

        self.bought_allocation_repo = FakeAllocationRepository()
        self.bought_demand_repo = FakeDemandRepository()
        self.use_case = GetOrders(
            order_repo=self.order_repo,
            order_item_repo=self.order_items,
            allocation_repo=self.bought_allocation_repo,
            demand_repo=self.bought_demand_repo,
            delivery_repo=FakeOrderItemDeliveryRepository(),
            source_allocation_repo=self.source_allocation_repo,
            source_demand_repo=self.source_demand_repo,
        )

    async def test_builds_demand_substitutions_for_a_source_line(self):
        result = await self.use_case.get_one(order_id=1)

        assert len(result.items) == 1
        item = result.items[0]
        assert len(item.demand_substitutions) == 1
        sub = item.demand_substitutions[0]
        assert sub.demand_item_id == 1
        assert sub.original_item_id == 1
        assert sub.original_item_article_name == "20x20x1000"
        assert sub.original_item_order_code_1 == "SRC-OC-1"
        assert sub.substitute_reason == "preferred supplier out of stock"
        assert sub.quantity == 4.0

    async def test_no_substitution_when_none_set(self):
        self.source_allocation.substitute_source_item_id = None
        result = await self.use_case.get_one(order_id=1)
        assert result.items[0].demand_substitutions == []

    async def test_falls_back_to_dimensionless_label_and_material_type_code(self):
        """No dimension -> "Source item #id"; no order_code_1 -> "material |
        type_name". This mirrors order_repository/_mappers.py's SOURCE-line
        label rules."""
        self.demand.source_item = make_source_item(
            id=1, dimension=None, order_code_1=None, material="Steel", type_name="Rod"
        )

        result = await self.use_case.get_one(order_id=1)

        sub = result.items[0].demand_substitutions[0]
        assert sub.original_item_article_name == "Source item #1"
        assert sub.original_item_order_code_1 == "Steel | Rod"

    async def test_bought_line_gets_no_source_substitutions(self):
        bought_line = make_order_item(id=2, order_id=1, bought_item_id=9)
        await self.order_items.save(bought_line)

        result = await self.use_case.get_one(order_id=1)

        bought_item_result = next(i for i in result.items if i.id == 2)
        assert bought_item_result.demand_substitutions == []

    async def test_missing_demand_is_skipped(self):
        self.source_demand_repo._demands.clear()
        result = await self.use_case.get_one(order_id=1)
        assert result.items[0].demand_substitutions == []

    async def test_a_bought_line_names_the_item_its_demand_asked_for(self):
        """A bought line substituting another catalogue item names the
        demand's own item, read off the demand rather than looked up."""
        bought_line = make_order_item(id=2, order_id=1, bought_item_id=9)
        await self.order_items.save(bought_line)
        original = make_bought_item(id=5, article_name="M6 screw")
        demand = make_demand(id=7)
        demand.item_id, demand.item = 5, original
        await self.bought_demand_repo.save(demand)
        allocation = make_allocation(demand_item_id=7, order_item_id=2, quantity=3.0)
        allocation.substitute_item_id = 9
        allocation.substitute_reason = "cheaper"
        await self.bought_allocation_repo.save(allocation)

        result = await self.use_case.get_one(order_id=1)

        bought = next(i for i in result.items if i.id == 2)
        assert [
            (s.demand_item_id, s.original_item_id, s.original_item_order_code_1, s.quantity)
            for s in bought.demand_substitutions
        ] == [(7, 5, "OC-5", 3.0)]
        assert bought.demand_substitutions[0].original_item_article_name == "M6 screw"
