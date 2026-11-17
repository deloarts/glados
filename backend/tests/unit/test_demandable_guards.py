"""
New work may only name an item that is active, not archived and, for made and
bought items, whose PDM file is not missing, and new demands need an active
project. Covered here on every path where a request newly names an item or a
project: demand creation, order lines, the substitute of an order line and the
material switch of a lot. No database, no HTTP.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.errors import BoughtItemInactiveError
from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.fulfillment.application.dto.bought_item_demand_dto import CreateDemandItemCommand
from src.modules.fulfillment.application.dto.made_item_demand_dto import CreateMadeItemDemandCommand
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    CreateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_demand_item import (
    CreateDemandItem as CreateBoughtDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.create_demand_item import (
    CreateDemandItem as CreateMadeDemand,
)
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.create_source_item_demand import (
    CreateSourceItemDemand,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.errors import ProjectInactiveError
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from tests.factories import make_user
from tests.unit import test_demand_item_use_cases as bought_demands
from tests.unit import test_made_item_demand_use_cases as made_demands
from tests.unit import test_source_item_demand_use_cases as source_demands
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order import _helpers as orders
from tests.unit.order._helpers import ExistingSuppliers
from tests.unit.production_lot import _helpers as lot_helpers
from tests.unit.production_lot import fakes as lot_fakes
from tests.unit.production_lot.fakes import FakeProjectRepository

MISSING = PdmSyncState.MISSING


# ── Bought item demands ──────────────────────────────────────────────────


class TestBoughtDemandCreation:
    def _use_case(self, item, project=None) -> CreateBoughtDemand:
        return CreateBoughtDemand(
            bought_demands.FakeDemandRepository(),
            bought_demands.FakeBoughtItemRepository([item]),
            bought_demands.FakeProjectRepository([project or bought_demands.make_project(id=1)]),
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(),
        )

    async def _create(self, use_case: CreateBoughtDemand):
        actor = bought_demands.make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        cmd = CreateDemandItemCommand(item_id=1, project_id=1, quantity=2.0, unit="pcs")
        return await use_case.execute(actor=actor, cmd=cmd)

    @pytest.mark.parametrize(
        ("changes", "reason"),
        [
            ({"status": BoughtItemCatalogueStatus.INACTIVE}, "is inactive"),
            ({"status": BoughtItemCatalogueStatus.REPLACED}, "is replaced"),
            ({"archived": True}, "is archived"),
            ({"pdm_sync_state": MISSING}, "is missing in PDM"),
        ],
    )
    async def test_an_item_new_work_may_not_name_is_refused(self, changes, reason):
        item = replace(bought_demands.make_bought_item(id=1), **changes)

        with pytest.raises(BoughtItemInactiveError, match=reason):
            await self._create(self._use_case(item))

    @pytest.mark.parametrize(
        "status", [ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED]
    )
    async def test_a_project_that_is_not_active_takes_no_demand(self, status):
        use_case = self._use_case(
            bought_demands.make_bought_item(id=1), bought_demands.make_project(status=status)
        )

        with pytest.raises(ProjectInactiveError):
            await self._create(use_case)

    async def test_an_active_item_and_project_take_the_demand(self):
        result = await self._create(self._use_case(bought_demands.make_bought_item(id=1)))

        assert result.status == "open"


# ── Made item demands ────────────────────────────────────────────────────


class TestMadeDemandCreation:
    def _use_case(self, item, project=None) -> CreateMadeDemand:
        return CreateMadeDemand(
            made_demands.FakeDemandRepository(),
            made_demands.FakeMadeItemRepository([item]),
            made_demands.FakeProjectRepository([project or made_demands.make_project(id=1)]),
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(),
        )

    async def _create(self, use_case: CreateMadeDemand):
        actor = made_demands.make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        cmd = CreateMadeItemDemandCommand(made_item_id=1, project_id=1, quantity=2.0, unit="pcs")
        return await use_case.execute(actor=actor, cmd=cmd)

    @pytest.mark.parametrize(
        ("changes", "reason"),
        [
            ({"status": MadeItemCatalogueStatus.REPLACED}, "is replaced"),
            ({"archived": True}, "is archived"),
            ({"pdm_sync_state": MISSING}, "is missing in PDM"),
        ],
    )
    async def test_an_item_new_work_may_not_name_is_refused(self, changes, reason):
        item = replace(made_demands.make_made_item(id=1), **changes)

        with pytest.raises(MadeItemInactiveError, match=reason):
            await self._create(self._use_case(item))

    async def test_a_project_on_hold_takes_no_demand(self):
        use_case = self._use_case(
            made_demands.make_made_item(id=1),
            made_demands.make_project(status=ProjectStatus.ON_HOLD),
        )

        with pytest.raises(ProjectInactiveError, match="on hold"):
            await self._create(use_case)


# ── Source item demands from a lot ───────────────────────────────────────


async def test_a_source_item_demand_needs_an_active_project():
    lot = source_demands.make_lot(source_item_id=1)
    project = replace(source_demands.make_project(id=1), status=ProjectStatus.COMPLETED)
    use_case = CreateSourceItemDemand(
        source_demands.FakeProductionLotRepository([lot]),
        source_demands.FakeSourceItemDemandRepository(),
        source_demands.FakeProjectRepository([project]),
        uow=FakeUnitOfWork(),
        reconciler=demand_reconciler(),
    )
    actor = source_demands.make_user(permissions=[Permission.WRITE_LOTS])

    with pytest.raises(ProjectInactiveError, match="completed"):
        await use_case.execute(actor, CreateSourceItemDemandCommand(lot_id=1, quantity=5.0))


# ── Order lines and substitutes ──────────────────────────────────────────


class _SourceItems:
    def __init__(self, items: list[SourceItem]) -> None:
        self._items = {item.id: item for item in items}

    async def get_by_id(self, id: int) -> SourceItem | None:
        return self._items.get(id)


class TestOrderLines:
    def _use_case(self, bought=None, source=None) -> CreateOrderItem:
        order_items = orders.FakeOrderItemRepository()
        order_repo = orders.FakeOrderRepository([orders.make_order(id=1, status=OrderStatus.DRAFT)])
        return CreateOrderItem(
            project_repo=FakeProjectRepository(),
            supplier_repo=ExistingSuppliers(),
            order_item_repo=order_items,
            item_repo=orders.FakeCatalogueRepository([bought] if bought else []),
            order_repo=order_repo,
            demand_repo=orders.FakeDemandRepository(),
            allocation_repo=orders.FakeAllocationRepository(),
            source_item_repo=_SourceItems([source] if source else []),
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(order_repo, order_items),
        )

    async def _create(self, use_case: CreateOrderItem, **reference):
        actor = make_user(permissions=[Permission.WRITE_ORDERS])
        cmd = CreateOrderItemCommand(
            order_id=1, supplier_id=1, project_id=1, quantity=3.0, unit="pcs", **reference
        )
        return await use_case.execute(actor=actor, cmd=cmd)

    @pytest.mark.parametrize(
        ("changes", "reason"),
        [
            ({"status": BoughtItemCatalogueStatus.INACTIVE}, "is inactive"),
            ({"archived": True}, "is archived"),
            ({"pdm_sync_state": MISSING}, "is missing in PDM"),
        ],
    )
    async def test_a_bought_line_needs_an_item_new_work_may_name(self, changes, reason):
        bought = replace(orders.make_bought_item(id=7), **changes)

        with pytest.raises(BoughtItemInactiveError, match=reason):
            await self._create(self._use_case(bought=bought), bought_item_id=7)

    @pytest.mark.parametrize(
        ("changes", "reason"),
        [
            ({"status": SourceItemCatalogueStatus.REPLACED}, "is replaced"),
            ({"archived": True}, "is archived"),
        ],
    )
    async def test_a_source_line_needs_an_item_new_work_may_name(self, changes, reason):
        source = replace(orders.make_source_item(id=3), **changes)

        with pytest.raises(SourceItemInactiveError, match=reason):
            await self._create(self._use_case(source=source), source_item_id=3)

    async def test_an_active_source_item_takes_the_line(self):
        result = await self._create(
            self._use_case(source=orders.make_source_item(id=3)), source_item_id=3
        )

        assert result.line_type == "SOURCE"


async def test_a_substitute_needs_an_item_new_work_may_name():
    substitute = replace(orders.make_bought_item(id=7), status=BoughtItemCatalogueStatus.REPLACED)
    order_items = orders.FakeOrderItemRepository([orders.make_order_item(id=1)])
    order_repo = orders.FakeOrderRepository([orders.make_order(id=1, status=OrderStatus.DRAFT)])
    use_case = UpdateOrderItem(
        order_item_repo=order_items,
        order_repo=order_repo,
        catalogue_repo=orders.FakeCatalogueRepository([substitute]),
        allocation_repo=orders.FakeAllocationRepository(),
        demand_repo=orders.FakeDemandRepository(),
        uow=FakeUnitOfWork(),
        reconciler=order_reconciler(order_repo, order_items),
        project_repo=FakeProjectRepository(),
    )
    actor = make_user(permissions=[Permission.WRITE_ORDERS])

    with pytest.raises(BoughtItemInactiveError, match="is replaced"):
        await use_case.execute(
            actor=actor,
            order_id=1,
            order_item_id=1,
            cmd=UpdateOrderItemCommand(quantity=10.0, unit="pcs", bought_item_id=7),
        )


# ── The material switch of a lot ────────────────────────────────────────


class TestMaterialSwitch:
    def setup_method(self) -> None:
        self.lot_repo = lot_fakes.FakeProductionLotRepository()

    def _use_case(self, bought=None, source=None, made=None) -> SwitchLotMaterialSource:
        return SwitchLotMaterialSource(
            lot_repo=self.lot_repo,
            bought_item_repo=lot_fakes.FakeBoughtItemRepository([bought] if bought else []),
            source_item_repo=lot_fakes.FakeSourceItemRepository([source] if source else []),
            made_item_repo=lot_fakes.FakeMadeItemRepository([made] if made else []),
            source_item_demand_repo=lot_fakes.FakeSourceItemDemandRepository(),
            source_item_allocation_repo=(
                allocations := lot_fakes.FakeSourceItemAllocationRepository()
            ),
            settings_repo=lot_fakes.FakeAdminSettingsRepository(),
            project_repo=lot_fakes.FakeProjectRepository(),
            line_release=lot_fakes.fake_line_release(allocations),
            uow=lot_fakes.FakeUnitOfWork(),
            reconciler=demand_reconciler(),
        )

    async def _switch(self, use_case: SwitchLotMaterialSource, **source):
        lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=None,
                changes=[],
                lot_number="LOT-1",
                quantity=5.0,
                status=LotStatus.DRAFT,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        return await use_case.execute(actor, lot.id, SwitchLotMaterialSourceCommand(**source))

    async def test_an_archived_bought_item_is_refused(self):
        bought = replace(lot_helpers.make_bought_item(id=4), archived=True)

        with pytest.raises(BoughtItemInactiveError, match="is archived"):
            await self._switch(self._use_case(bought=bought), bought_item_id=4)

    async def test_an_inactive_source_item_is_refused(self):
        source = lot_helpers.make_source_item(id=5, status=SourceItemCatalogueStatus.INACTIVE)

        with pytest.raises(SourceItemInactiveError, match="is inactive"):
            await self._switch(self._use_case(source=source), source_item_id=5)

    async def test_a_made_item_whose_file_is_missing_is_refused(self):
        made = replace(lot_helpers.make_made_item(id=6), pdm_sync_state=MISSING)

        with pytest.raises(MadeItemInactiveError, match="is missing in PDM"):
            await self._switch(self._use_case(made=made), made_item_id=6)

    async def test_an_active_bought_item_is_taken(self):
        result = await self._switch(
            self._use_case(bought=lot_helpers.make_bought_item(id=4)), bought_item_id=4
        )

        assert result.source_bought_item_id == 4
