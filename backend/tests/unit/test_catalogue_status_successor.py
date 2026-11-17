"""
Status and successor of made, bought and source items through their update
and create use cases: a replaced item names a successor that exists, is not
archived and does not lead back, only a replaced item names one, moving to
active or inactive drops it, and a status change publishes the catalogue's
status event. No database, no HTTP.
"""

from typing import Any

import pytest

from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemCommand
from src.modules.catalogue.application.dto.source_item_dto import CreateSourceItemCommand
from src.modules.catalogue.application.dto.source_item_dto import UpdateSourceItemCommand
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.update_made_item import UpdateMadeItem
from src.modules.catalogue.application.use_cases.source_item.create_source_item import (
    CreateSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item import (
    UpdateSourceItem,
)
from src.modules.catalogue.domain.errors import BoughtItemInactiveError
from src.modules.catalogue.domain.errors import CatalogueStatusChangeError
from src.modules.catalogue.domain.errors import CatalogueSuccessorNotFoundError
from src.modules.catalogue.domain.errors import PdmSuccessorRequiresReplacedStatusError
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemStatusChanged
from src.modules.catalogue.domain.events.source_item_events import SourceItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item import _helpers as made_helpers
from tests.unit.made_item import fakes as made_fakes
from tests.unit.made_item.fakes import FakeCustomerRepository
from tests.unit.test_bought_item_use_cases import FakeAdminSettingsRepository as BoughtSettings
from tests.unit.test_bought_item_use_cases import FakeArticleGroupRepository as BoughtGroups
from tests.unit.test_bought_item_use_cases import FakeBoughtItemRepository
from tests.unit.test_bought_item_use_cases import FakePartNumberRegistry
from tests.unit.test_bought_item_use_cases import FakeSupplierRepository
from tests.unit.test_bought_item_use_cases import make_bought_item
from tests.unit.test_bought_item_use_cases import make_pdm_settings
from tests.unit.test_bought_item_use_cases import make_supplier
from tests.unit.test_source_item_use_cases import FakeSourceItemRepository
from tests.unit.test_source_item_use_cases import FakeSourceItemTypeRepository
from tests.unit.test_source_item_use_cases import FakeSupplierRepository as SourceSuppliers
from tests.unit.test_source_item_use_cases import make_source_item
from tests.unit.test_source_item_use_cases import make_source_item_type

ACTOR_ID = 1


class _Cases:
    """The rule seen through one catalogue's update use case. A subclass
    supplies the catalogue: its items, its use case and its command."""

    event_type: type
    item_repo: Any

    def setup_method(self) -> None:
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()

    def _item(self, id: int, status: str = "active", archived: bool = False) -> Any:
        raise NotImplementedError

    def _use_case(self) -> Any:
        raise NotImplementedError

    def _cmd(self, item: Any, **overrides: Any) -> Any:
        raise NotImplementedError

    async def _update(self, item: Any, **overrides: Any) -> Any:
        return await self._use_case().execute(
            actor=self.actor, item_id=item.id, cmd=self._cmd(item, **overrides)
        )

    def _status_events(self) -> list[Any]:
        return [e for e in self.bus.published if isinstance(e, self.event_type)]

    async def test_replacing_with_a_live_successor_stores_it_and_publishes_the_change(self):
        item = self._item(1)
        self._item(2)

        result = await self._update(item, status="replaced", successor_item_id=2)

        assert result.status == "replaced"
        assert result.successor_item_id == 2
        (event,) = self._status_events()
        assert (event.item_id, event.old_status, event.new_status) == (1, "active", "replaced")
        assert event.actor_id == ACTOR_ID
        assert self.uow.committed

    async def test_replacing_without_a_successor_is_refused(self):
        item = self._item(1)

        with pytest.raises(CatalogueStatusChangeError, match="needs a successor"):
            await self._update(item, status="replaced", successor_item_id=None)

        assert item.status == "active"
        assert not self.uow.committed
        assert self.bus.published == []

    async def test_a_successor_that_does_not_exist_is_not_found(self):
        item = self._item(1)

        with pytest.raises(CatalogueSuccessorNotFoundError, match="#99"):
            await self._update(item, status="replaced", successor_item_id=99)

    async def test_an_archived_successor_is_refused(self):
        item = self._item(1)
        self._item(2, archived=True)

        with pytest.raises(CatalogueStatusChangeError, match="archived"):
            await self._update(item, status="replaced", successor_item_id=2)

    async def test_a_successor_that_leads_back_is_refused(self):
        item = self._item(1)
        successor = self._item(2, status="replaced")
        successor.successor_item_id = 1

        with pytest.raises(CatalogueStatusChangeError, match="loop"):
            await self._update(item, status="replaced", successor_item_id=2)

    async def test_an_item_cannot_succeed_itself(self):
        item = self._item(1)

        with pytest.raises(CatalogueStatusChangeError, match="its own successor"):
            await self._update(item, status="replaced", successor_item_id=1)

    async def test_moving_back_to_active_drops_the_successor_the_form_sends_back(self):
        item = self._item(1, status="replaced")
        item.successor_item_id = 2
        self._item(2)

        result = await self._update(item, status="active", successor_item_id=2)

        assert result.status == "active"
        assert result.successor_item_id is None
        assert "successor_item_id: 2 → None" in item.changes[-1]
        (event,) = self._status_events()
        assert (event.old_status, event.new_status) == ("replaced", "active")

    async def test_naming_a_successor_without_replacing_is_refused(self):
        item = self._item(1)
        self._item(2)

        with pytest.raises(CatalogueStatusChangeError, match="only a replaced item"):
            await self._update(item, successor_item_id=2)

    async def test_an_older_replaced_row_without_successor_stays_editable(self):
        item = self._item(1, status="replaced")

        result = await self._update(item, note="Edited")

        assert result.status == "replaced"
        assert result.successor_item_id is None
        assert self._status_events() == []

    async def test_an_edit_that_keeps_the_status_publishes_no_status_event(self):
        item = self._item(1)

        await self._update(item, note="Edited")

        assert self._status_events() == []


class TestBoughtItem(_Cases):
    event_type = BoughtItemStatusChanged

    def setup_method(self) -> None:
        super().setup_method()
        self.item_repo = FakeBoughtItemRepository([])
        self.settings = BoughtSettings()
        self.actor = make_user(id=ACTOR_ID, permissions=[Permission.WRITE_BOUGHT_ITEMS])

    def _item(
        self,
        id: int,
        status: str = "active",
        archived: bool = False,
    ) -> Any:
        # The shared cases name the status, as all three catalogues share it.
        item = make_bought_item(id=id, status=BoughtItemCatalogueStatus(status), archived=archived)
        self.item_repo._items[id] = item
        return item

    def _use_case(self) -> UpdateBoughtItem:
        return UpdateBoughtItem(
            self.item_repo,
            FakeSupplierRepository([make_supplier(id=1)]),
            BoughtGroups(),
            self.settings,
            part_number_registry=FakePartNumberRegistry(),
            uow=self.uow,
            event_bus=self.bus,
            cad_source=PdmCadSource(self.settings),
        )

    def _cmd(self, item: Any, **overrides: Any) -> UpdateBoughtItemCommand:
        values = dict(
            order_code_1=item.order_code_1,
            order_code_2=item.order_code_2,
            gtin=item.gtin,
            ean=item.ean,
            tariff_number=item.tariff_number,
            article_name=item.article_name,
            article_group_ids=list(item.article_group_ids),
            status=item.status,
            part_number=item.part_number,
            mass=item.mass,
            note=item.note,
            weblink=item.weblink,
            manufacturer_id=item.manufacturer_id,
            successor_item_id=item.successor_item_id,
        )
        values.update(overrides)
        return UpdateBoughtItemCommand(**values)

    async def test_a_cad_row_may_drop_the_successor_while_pdm_owns_its_status(self):
        self.settings = BoughtSettings(pdm=make_pdm_settings(enabled=True))
        item = self._item(1, status=BoughtItemCatalogueStatus.REPLACED)
        item.data_source = DataSource.CAD
        item.successor_item_id = 2
        self._item(2)

        result = await self._update(item, successor_item_id=None)

        assert result.status == "replaced"
        assert result.successor_item_id is None

    async def test_the_pdm_gate_answers_before_the_successor_is_looked_up(self):
        self.settings = BoughtSettings(pdm=make_pdm_settings(enabled=True))
        item = self._item(1)
        item.data_source = DataSource.CAD

        with pytest.raises(PdmSuccessorRequiresReplacedStatusError):
            await self._update(item, successor_item_id=99)

    async def test_without_a_bus_the_status_still_changes(self):
        item = self._item(1)
        self._item(2)
        use_case = UpdateBoughtItem(
            self.item_repo,
            FakeSupplierRepository([make_supplier(id=1)]),
            BoughtGroups(),
            self.settings,
            part_number_registry=FakePartNumberRegistry(),
            uow=self.uow,
            cad_source=PdmCadSource(self.settings),
        )

        result = await use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(item, status="replaced", successor_item_id=2),
        )

        assert result.successor_item_id == 2


class TestMadeItem(_Cases):
    event_type = MadeItemStatusChanged

    def setup_method(self) -> None:
        super().setup_method()
        self.item_repo = made_fakes.FakeMadeItemRepository([])
        self.bought_items = made_fakes.FakeBoughtItemRepository(
            [made_helpers.make_bought_item(id=1, status=BoughtItemCatalogueStatus.INACTIVE)]
        )
        self.actor = make_user(id=ACTOR_ID, permissions=[Permission.WRITE_MADE_ITEMS])

    def _item(
        self,
        id: int,
        status: str = "active",
        archived: bool = False,
    ) -> Any:
        # The shared cases name the status, as all three catalogues share it.
        item = made_helpers.make_made_item(
            id=id, status=MadeItemCatalogueStatus(status), archived=archived
        )
        self.item_repo._items[id] = item
        return item

    def _use_case(self) -> UpdateMadeItem:
        return UpdateMadeItem(
            self.item_repo,
            made_fakes.FakeArticleGroupRepository(),
            self.bought_items,
            made_fakes.FakeSourceItemRepository(),
            made_fakes.FakeAdminSettingsRepository(),
            part_number_registry=made_fakes.FakePartNumberRegistry(),
            uow=self.uow,
            event_bus=self.bus,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(made_fakes.FakeAdminSettingsRepository()),
        )

    def _cmd(self, item: Any, **overrides: Any) -> UpdateMadeItemCommand:
        values = dict(
            article_name=item.article_name,
            article_group_ids=list(item.article_group_ids),
            status=item.status,
            part_number=item.part_number,
            material=item.material,
            mass=item.mass,
            base_size=item.base_size,
            note=item.note,
            weblink=item.weblink,
            bought_item_id=item.bought_item_id,
            source_item_id=item.source_item_id,
            successor_item_id=item.successor_item_id,
        )
        values.update(overrides)
        return UpdateMadeItemCommand(**values)

    async def test_a_material_that_turned_inactive_later_does_not_block_retiring(self):
        item = self._item(1)
        item.bought_item_id = 1

        result = await self._update(item, status="inactive")

        assert result.status == "inactive"
        assert result.bought_item_id == 1

    async def test_naming_an_inactive_material_is_refused(self):
        # A CAD row with PDM off, so the revision policy of a web row does
        # not stand in front of the material check.
        item = self._item(1)
        item.data_source = DataSource.CAD

        with pytest.raises(BoughtItemInactiveError):
            await self._update(item, bought_item_id=1)


class TestSourceItem(_Cases):
    event_type = SourceItemStatusChanged

    def setup_method(self) -> None:
        super().setup_method()
        self.item_repo = FakeSourceItemRepository([])
        self.actor = make_user(id=ACTOR_ID, permissions=[Permission.WRITE_SOURCE_ITEMS])

    def _item(
        self,
        id: int,
        status: str = "active",
        archived: bool = False,
    ) -> Any:
        # The shared cases name the status, as all three catalogues share it.
        item = make_source_item(id=id, status=SourceItemCatalogueStatus(status), archived=archived)
        # Distinct dimensions, so no item is a duplicate spec of another.
        item.dimension = f"{id * 10}mm"
        self.item_repo._items[id] = item
        return item

    def _use_case(self) -> UpdateSourceItem:
        return UpdateSourceItem(
            self.item_repo,
            SourceSuppliers([]),
            FakeSourceItemTypeRepository([make_source_item_type(id=1)]),
            uow=self.uow,
            event_bus=self.bus,
        )

    def _cmd(self, item: Any, **overrides: Any) -> UpdateSourceItemCommand:
        values = dict(
            type_id=item.type_id,
            dimension=item.dimension,
            material=item.material,
            mass=item.mass,
            note=item.note,
            order_code_1=item.order_code_1,
            order_code_2=item.order_code_2,
            status=item.status,
            manufacturer_id=item.manufacturer_id,
            approver_id=item.approver_id,
            successor_item_id=item.successor_item_id,
        )
        values.update(overrides)
        return UpdateSourceItemCommand(**values)


# ── Creation: a new item names no successor, so it cannot start replaced ──


async def test_a_bought_item_cannot_be_created_replaced():
    use_case = CreateBoughtItem(
        FakeBoughtItemRepository([]),
        FakeSupplierRepository([make_supplier(id=1)]),
        BoughtGroups(),
        BoughtSettings(),
        part_number_registry=FakePartNumberRegistry(),
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
        cad_source=PdmCadSource(BoughtSettings()),
    )
    actor = make_user(permissions=[Permission.WRITE_BOUGHT_ITEMS])
    cmd = CreateBoughtItemCommand(
        order_code_1="OC-1", article_name="Bolt", manufacturer_id=1, status="replaced"
    )

    with pytest.raises(CatalogueStatusChangeError, match="A new bought item needs a successor"):
        await use_case.prepare(actor, cmd)


async def test_a_made_item_cannot_be_created_replaced():
    use_case = CreateMadeItem(
        made_fakes.FakeMadeItemRepository([]),
        made_fakes.FakeArticleGroupRepository(),
        made_fakes.FakeBoughtItemRepository(),
        made_fakes.FakeSourceItemRepository(),
        made_fakes.FakeFabricationMethodRepository([]),
        made_fakes.FakeInspectionMethodRepository([]),
        made_fakes.FakeAdminSettingsRepository(),
        part_number_registry=made_fakes.FakePartNumberRegistry(),
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
        customer_repo=FakeCustomerRepository(),
        cad_source=PdmCadSource(made_fakes.FakeAdminSettingsRepository()),
    )
    actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
    cmd = CreateMadeItemCommand(revision="A", article_name="Bracket", status="replaced")

    with pytest.raises(CatalogueStatusChangeError, match="A new made item needs a successor"):
        await use_case.prepare(actor, cmd)


async def test_a_source_item_cannot_be_created_replaced():
    use_case = CreateSourceItem(
        FakeSourceItemRepository([]),
        SourceSuppliers([]),
        FakeSourceItemTypeRepository([make_source_item_type(id=1)]),
        uow=FakeUnitOfWork(),
    )
    actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])
    cmd = CreateSourceItemCommand(type_id=1, dimension="40mm", material="1.0037", status="replaced")

    with pytest.raises(CatalogueStatusChangeError, match="A new source item needs a successor"):
        await use_case.execute(actor, cmd)


@pytest.mark.parametrize("status", ["active", "inactive"])
async def test_a_source_item_may_be_created_active_or_inactive(status):
    use_case = CreateSourceItem(
        FakeSourceItemRepository([]),
        SourceSuppliers([]),
        FakeSourceItemTypeRepository([make_source_item_type(id=1)]),
        uow=FakeUnitOfWork(),
    )
    actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])
    cmd = CreateSourceItemCommand(type_id=1, dimension="40mm", material="1.0037", status=status)

    result = await use_case.execute(actor, cmd)

    assert result.status == status
    assert result.successor_item_id is None
