"""
Unit tests for the line type rules of CreateOrderItem and UpdateOrderItem:
each creation branch stamps the type that matches its catalogue reference,
and an update may not set fields that belong to another line type. No
database, no HTTP; every dependency is an in-memory fake.
"""

import pytest

from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemLineTypeMismatchError
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import ExistingSuppliers
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeCatalogueRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeSourceItemRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_bought_item
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.production_lot.fakes import FakeProjectRepository


class TestCreateOrderItemLineType:
    """Each of the three creation branches must stamp the line type that
    matches the catalogue reference it was given. A branch that falls
    through to the BOUGHT default leaves free-text lines indistinguishable
    from catalogue lines in the database."""

    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order_repo = FakeOrderRepository([make_order(id=1, status=OrderStatus.DRAFT)])
        self.order_item_repo = FakeOrderItemRepository()
        self.uow = FakeUnitOfWork()

    def _use_case(self, catalogue: FakeCatalogueRepository | None = None) -> CreateOrderItem:
        return CreateOrderItem(
            project_repo=FakeProjectRepository(),
            supplier_repo=ExistingSuppliers(),
            order_item_repo=self.order_item_repo,
            item_repo=catalogue or FakeCatalogueRepository(),
            order_repo=self.order_repo,
            demand_repo=FakeDemandRepository(),
            allocation_repo=FakeAllocationRepository(),
            source_item_repo=FakeSourceItemRepository(),
            uow=self.uow,
            reconciler=order_reconciler(self.order_repo, self.order_item_repo),
        )

    def _cmd(self, **overrides) -> CreateOrderItemCommand:
        return CreateOrderItemCommand(
            **{
                "order_id": 1,
                "supplier_id": 1,
                "project_id": 1,
                "quantity": 3.0,
                "unit": "pcs",
                **overrides,
            }
        )

    async def test_free_text_line_is_typed_virtual(self):
        result = await self._use_case().execute(
            actor=self.actor, cmd=self._cmd(virtual_name="Crating and export packing")
        )

        assert result.line_type == "VIRTUAL"
        assert result.virtual_name == "Crating and export packing"
        assert result.bought_item_id is None

    async def test_catalogue_line_is_typed_bought(self):
        catalogue = FakeCatalogueRepository([make_bought_item(id=7)])

        result = await self._use_case(catalogue).execute(
            actor=self.actor, cmd=self._cmd(bought_item_id=7)
        )

        assert result.line_type == "BOUGHT"
        assert result.bought_item_id == 7
        # A catalogue line stores no name of its own.
        assert result.virtual_name is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"bought_item_id": 7, "virtual_name": "both"},
            {"bought_item_id": 7, "source_item_id": 3},
        ],
        ids=["none", "bought-and-virtual", "bought-and-source"],
    )
    def test_command_requires_exactly_one_catalogue_reference(self, kwargs):
        with pytest.raises(ValueError, match="Exactly one of bought_item_id"):
            self._cmd(**kwargs)

    async def test_use_case_rejects_a_command_that_bypasses_dto_validation(self):
        # OrderRules.assert_valid_line_type is
        # defence in depth behind the DTO validator above, normally
        # unreachable through CreateOrderItemCommand's own constructor, so
        # this reaches it via model_construct(), which skips pydantic
        # validation entirely, the same way a future caller that builds
        # the command by hand (not via .model_validate) could.
        cmd = CreateOrderItemCommand.model_construct(
            order_id=1,
            supplier_id=1,
            project_id=1,
            quantity=3.0,
            unit="pcs",
            bought_item_id=7,
            source_item_id=3,
            virtual_name=None,
            price=None,
            note=None,
            expected_delivery_date=None,
            expected_pickup_date=None,
            substitute_reason=None,
        )
        catalogue = FakeCatalogueRepository([make_bought_item(id=7)])
        with pytest.raises(OrderItemLineTypeMismatchError):
            await self._use_case(catalogue).execute(actor=self.actor, cmd=cmd)


class TestUpdateOrderItemLineTypeGuards:
    """virtual_name and bought-item substitution each belong to exactly one
    line type. A MADE line's name comes from its lot's made item and a SOURCE
    line's from its source item, so neither may be overwritten here, the
    fields would be silently ignored on read and diverge from the
    catalogue."""

    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order_repo = FakeOrderRepository([make_order(id=1, status=OrderStatus.DRAFT)])
        self.catalogue = FakeCatalogueRepository([make_bought_item(id=7)])
        self.uow = FakeUnitOfWork()

    def _use_case(self, item: OrderItem) -> UpdateOrderItem:
        order_item_repo = FakeOrderItemRepository([item])
        return UpdateOrderItem(
            order_item_repo=order_item_repo,
            order_repo=self.order_repo,
            catalogue_repo=self.catalogue,
            allocation_repo=FakeAllocationRepository(),
            demand_repo=FakeDemandRepository(),
            uow=self.uow,
            reconciler=order_reconciler(self.order_repo, order_item_repo),
            project_repo=FakeProjectRepository(),
        )

    def _cmd(self, **overrides) -> UpdateOrderItemCommand:
        return UpdateOrderItemCommand(**{"quantity": 10.0, "unit": "pcs", **overrides})

    def _made_line(self) -> OrderItem:
        item = make_order_item(id=1)
        item.line_type = OrderLineType.MADE
        item.bought_item_id = None
        item.lot_position_id = 5
        return item

    async def test_rejects_a_virtual_name_on_a_made_line(self):
        use_case = self._use_case(self._made_line())

        with pytest.raises(OrderItemLineTypeMismatchError, match="only VIRTUAL"):
            await use_case.execute(
                actor=self.actor,
                order_id=1,
                order_item_id=1,
                cmd=self._cmd(virtual_name="Renamed by hand"),
            )
        assert not self.uow.committed

    async def test_rejects_a_virtual_name_on_a_base_line(self):
        item = make_order_item(id=1)
        item.line_type = OrderLineType.SOURCE
        item.bought_item_id = None
        item.source_item_id = 3

        with pytest.raises(OrderItemLineTypeMismatchError, match="only VIRTUAL"):
            await self._use_case(item).execute(
                actor=self.actor,
                order_id=1,
                order_item_id=1,
                cmd=self._cmd(virtual_name="Renamed by hand"),
            )

    async def test_rejects_substituting_a_catalogue_item_onto_a_made_line(self):
        use_case = self._use_case(self._made_line())

        with pytest.raises(OrderItemLineTypeMismatchError, match="cannot be repointed"):
            await use_case.execute(
                actor=self.actor, order_id=1, order_item_id=1, cmd=self._cmd(bought_item_id=7)
            )
        # Rejected before the catalogue was consulted at all.
        assert self.catalogue.lookups == []

    async def test_attaching_a_catalogue_item_promotes_a_virtual_line_to_bought(self):
        """The one identity change that legitimately crosses line types:
        a free-text line turning out to be a stock part. The free-text
        name must not survive the promotion."""
        item = make_order_item(id=1)
        item.line_type = OrderLineType.VIRTUAL
        item.bought_item_id = None
        item.virtual_name = "Probably a hex bolt"

        result = await self._use_case(item).execute(
            actor=self.actor, order_id=1, order_item_id=1, cmd=self._cmd(bought_item_id=7)
        )

        assert result.line_type == "BOUGHT"
        assert result.bought_item_id == 7
        assert result.virtual_name is None

    async def test_allows_renaming_a_virtual_line(self):
        item = make_order_item(id=1)
        item.line_type = OrderLineType.VIRTUAL
        item.bought_item_id = None
        item.virtual_name = "Old name"

        result = await self._use_case(item).execute(
            actor=self.actor, order_id=1, order_item_id=1, cmd=self._cmd(virtual_name="New name")
        )

        assert result.virtual_name == "New name"

    async def test_allows_substitution_on_a_bought_line(self):
        result = await self._use_case(make_order_item(id=1)).execute(
            actor=self.actor, order_id=1, order_item_id=1, cmd=self._cmd(bought_item_id=7)
        )

        assert result.bought_item_id == 7

    async def test_rejects_saving_an_already_corrupted_item_even_when_untouched(self):
        # OrderRules.assert_valid_line_type
        # runs after every update regardless of which fields changed, so
        # pre-existing bad data (e.g. a legacy row with two identity FKs
        # set) is caught on its next save rather than silently persisted
        # forward, including on a quantity-only update that neither of the
        # two explicit guards above (virtual_name / bought_item_id) would see.
        item = make_order_item(id=1)
        item.line_type = OrderLineType.SOURCE
        item.bought_item_id = None
        item.source_item_id = 3
        item.virtual_name = "should not coexist with source_item_id"

        with pytest.raises(OrderItemLineTypeMismatchError):
            await self._use_case(item).execute(
                actor=self.actor,
                order_id=1,
                order_item_id=1,
                cmd=self._cmd(),
            )
