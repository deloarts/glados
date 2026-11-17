"""
Enforcement tests for docs/FIELD_OWNERSHIP.md principle 3 (PDM-owned fields
are read-only on a CAD row while the integration is enabled and the admin's
CAD-items-read-only override is on) across the use cases that write
made/bought items: UpdateMadeItem, UpdateBoughtItem, CreateMadeItemRevision,
MergeMadeItem, MergeBoughtItem. No database, no HTTP. Reuses the fakes and
make_*() helpers from the item use-case test modules rather than
duplicating them; test_pdm_ownership.py covers the domain service itself in
isolation.
"""

import pytest

from src.modules.catalogue.application.dto.bought_item_dto import MergeBoughtItemCommand
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionItemCommand
from src.modules.catalogue.application.dto.made_item_dto import MergeMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemCommand
from src.modules.catalogue.application.use_cases.bought_item.merge_bought_item import (
    MergeBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.merge_made_item import MergeMadeItem
from src.modules.catalogue.application.use_cases.made_item.update_made_item import UpdateMadeItem
from src.modules.catalogue.domain.errors import MadeItemRevisionManagedByPdmError
from src.modules.catalogue.domain.errors import PdmOwnedFieldReadOnlyError
from src.modules.catalogue.domain.errors import PdmSuccessorRequiresReplacedStatusError
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeBoughtItemUsages
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeMadeItemUsages
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.item_picture_fakes import FakeItemPictureRepository
from tests.unit.made_item._helpers import make_fabrication_method
from tests.unit.made_item._helpers import make_inspection_method
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_pdm_settings as make_made_pdm_settings
from tests.unit.made_item.fakes import FakeAdminSettingsRepository as MadeSettingsRepo
from tests.unit.made_item.fakes import FakeArticleGroupRepository
from tests.unit.made_item.fakes import FakeBoughtItemRepository as MadeBoughtItemRepo
from tests.unit.made_item.fakes import FakeCustomerRepository
from tests.unit.made_item.fakes import FakeFabricationMethodRepository
from tests.unit.made_item.fakes import FakeInspectionMethodRepository
from tests.unit.made_item.fakes import FakeMadeItemFileRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository
from tests.unit.made_item.fakes import FakePartNumberRegistry
from tests.unit.made_item.fakes import FakeSourceItemRepository
from tests.unit.test_bought_item_use_cases import FakeAdminSettingsRepository as BoughtSettingsRepo
from tests.unit.test_bought_item_use_cases import FakeArticleGroupRepository as BoughtArticleGroups
from tests.unit.test_bought_item_use_cases import FakeBoughtItemFileRepository
from tests.unit.test_bought_item_use_cases import FakeBoughtItemRepository
from tests.unit.test_bought_item_use_cases import FakeSupplierRepository
from tests.unit.test_bought_item_use_cases import make_bought_item
from tests.unit.test_bought_item_use_cases import make_pdm_settings as make_bought_pdm_settings
from tests.unit.test_bought_item_use_cases import make_supplier

# ── UpdateMadeItem ────────────────────────────────────────────────────


class TestUpdateMadeItemPdmEnforcement:
    def setup_method(self):
        self.item = make_made_item(id=1, article_name="Bracket")
        self.item.data_source = DataSource.CAD
        self.item_repo = FakeMadeItemRepository([self.item])
        self.article_group_repo = FakeArticleGroupRepository()
        self.bought_item_repo = MadeBoughtItemRepo([])
        self.source_item_repo = FakeSourceItemRepository()
        self.registry = FakePartNumberRegistry()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.system_actor = make_user(
            id=2, username="system", permissions=[Permission.WRITE_MADE_ITEMS], is_systemuser=True
        )

    def _use_case(self, admin_settings_repo: MadeSettingsRepo) -> UpdateMadeItem:
        return UpdateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            admin_settings_repo,
            part_number_registry=self.registry,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(admin_settings_repo),
        )

    def _cmd(self, **kwargs) -> UpdateMadeItemCommand:
        defaults = dict(
            article_name=self.item.article_name,
            article_group_ids=list(self.item.article_group_ids),
            status=self.item.status,
            part_number=self.item.part_number,
            material=self.item.material,
            mass=self.item.mass,
            base_size=self.item.base_size,
            note=self.item.note,
            weblink=self.item.weblink,
            bought_item_id=self.item.bought_item_id,
            source_item_id=self.item.source_item_id,
            successor_item_id=self.item.successor_item_id,
        )
        defaults.update(kwargs)
        return UpdateMadeItemCommand(**defaults)

    async def test_enforcement_off_allows_pdm_owned_change_on_cad_row(self):
        # Default FakeAdminSettingsRepository seeds PDM disabled, so enforce
        # is False and even a CAD row's addin-owned field stays editable.
        use_case = self._use_case(MadeSettingsRepo())
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(article_name="Renamed")
        )
        assert result.article_name == "Renamed"

    async def test_enforcement_on_web_row_allows_change(self):
        self.item.data_source = DataSource.WEB
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(weblink="https://example.com")
        )
        assert result.weblink == "https://example.com"

    async def test_enforcement_on_cad_row_blocks_addin_owned_change(self):
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            await use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(article_name="Renamed")
            )
        assert "article_name" in str(exc_info.value)

    async def test_enforcement_on_cad_row_blocks_status_change(self):
        # Lifecycle status feature: status is PDM-owned, so it is blocked
        # on a CAD row under enforcement the same way any other PDM/
        # add-in-owned field is. See test_enforcement_on_cad_row_blocks_
        # addin_owned_change below for the general case.
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(status="inactive"))
        assert "status" in str(exc_info.value)

    async def test_enforcement_on_cad_row_allows_clearing_successor(self):
        self.item.successor_item_id = 99
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(successor_item_id=None)
        )
        assert result.successor_item_id is None

    async def test_enforcement_on_cad_row_allows_successor_when_status_is_replaced(self):
        self.item.status = MadeItemCatalogueStatus.REPLACED
        # The successor must exist: a nonexistent one is refused as not found.
        await self.item_repo.save(make_made_item(id=7, article_name="Bracket Mk2"))
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(status="replaced", successor_item_id=7),
        )
        assert result.successor_item_id == 7

    async def test_enforcement_on_cad_row_rejects_successor_when_not_replaced(self):
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmSuccessorRequiresReplacedStatusError):
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(successor_item_id=7))

    async def test_cad_items_read_only_off_allows_change(self):
        # The admin override lifts the web restriction without changing
        # ownership (docs/FIELD_OWNERSHIP.md principle 3).
        settings = MadeSettingsRepo(
            pdm=make_made_pdm_settings(enabled=True, cad_items_read_only=False)
        )
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(article_name="Renamed")
        )
        assert result.article_name == "Renamed"

    async def test_system_user_bypasses_enforcement(self):
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.system_actor, item_id=1, cmd=self._cmd(article_name="Renamed")
        )
        assert result.article_name == "Renamed"

    async def test_renumbering_a_cad_row_is_blocked(self):
        self.item.part_number = "SW-001"
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="SW-002"))
        assert "part_number" in str(exc_info.value)


# ── UpdateBoughtItem ──────────────────────────────────────────────────


class TestUpdateBoughtItemPdmEnforcement:
    def setup_method(self):
        self.item = make_bought_item(id=1, article_name="Hex Bolt M8")
        self.item.data_source = DataSource.CAD
        self.item_repo = FakeBoughtItemRepository([self.item])
        self.supplier_repo = FakeSupplierRepository([make_supplier(id=1)])
        self.article_group_repo = BoughtArticleGroups()
        self.registry = FakePartNumberRegistry()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_BOUGHT_ITEMS])
        self.system_actor = make_user(
            id=2,
            username="system",
            permissions=[Permission.WRITE_BOUGHT_ITEMS],
            is_systemuser=True,
        )

    def _use_case(self, admin_settings_repo: BoughtSettingsRepo) -> UpdateBoughtItem:
        return UpdateBoughtItem(
            self.item_repo,
            self.supplier_repo,
            self.article_group_repo,
            admin_settings_repo,
            part_number_registry=self.registry,
            uow=self.uow,
            cad_source=PdmCadSource(admin_settings_repo),
        )

    def _cmd(self, **kwargs) -> UpdateBoughtItemCommand:
        defaults = dict(
            order_code_1=self.item.order_code_1,
            order_code_2=self.item.order_code_2,
            gtin=self.item.gtin,
            ean=self.item.ean,
            tariff_number=self.item.tariff_number,
            article_name=self.item.article_name,
            article_group_ids=list(self.item.article_group_ids),
            status=self.item.status,
            part_number=self.item.part_number,
            mass=self.item.mass,
            note=self.item.note,
            weblink=self.item.weblink,
            manufacturer_id=self.item.manufacturer_id,
            successor_item_id=self.item.successor_item_id,
        )
        defaults.update(kwargs)
        return UpdateBoughtItemCommand(**defaults)

    async def test_enforcement_off_allows_pdm_owned_change_on_cad_row(self):
        use_case = self._use_case(BoughtSettingsRepo())
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(article_name="Renamed")
        )
        assert result.article_name == "Renamed"

    async def test_enforcement_on_web_row_allows_change(self):
        self.item.data_source = DataSource.WEB
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(weblink="https://example.com")
        )
        assert result.weblink == "https://example.com"

    async def test_enforcement_on_cad_row_blocks_addin_owned_change(self):
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            await use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(article_name="Renamed")
            )
        assert "article_name" in str(exc_info.value)

    async def test_enforcement_on_cad_row_blocks_status_change(self):
        # Lifecycle status feature: status is PDM-owned. See the matching
        # made-item test's comment.
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(status="inactive"))
        assert "status" in str(exc_info.value)

    async def test_enforcement_on_cad_row_allows_clearing_successor(self):
        self.item.successor_item_id = 99
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(successor_item_id=None)
        )
        assert result.successor_item_id is None

    async def test_enforcement_on_cad_row_allows_successor_when_status_is_replaced(self):
        self.item.status = BoughtItemCatalogueStatus.REPLACED
        # The successor must exist: a nonexistent one is refused as not found.
        await self.item_repo.save(make_bought_item(id=7, article_name="Hex Bolt M8 A2"))
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(status="replaced", successor_item_id=7),
        )
        assert result.successor_item_id == 7

    async def test_enforcement_on_cad_row_rejects_successor_when_not_replaced(self):
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmSuccessorRequiresReplacedStatusError):
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(successor_item_id=7))

    async def test_system_user_bypasses_enforcement(self):
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.system_actor, item_id=1, cmd=self._cmd(article_name="Renamed")
        )
        assert result.article_name == "Renamed"

    async def test_renumbering_a_cad_row_is_blocked(self):
        self.item.part_number = "SW-001"
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="SW-002"))
        assert "part_number" in str(exc_info.value)


# ── CreateMadeItemRevision ────────────────────────────────────────────


class TestCreateMadeItemRevisionSystemUserBypass:
    """test_made_item_revision_use_cases.py::test_cad_item_rejected already
    pins the human-actor rejection; this covers the system-user bypass this
    effort adds (ingest creates CAD-family revisions through this use
    case, docs/FIELD_OWNERSHIP.md principle 6)."""

    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item.part_number = "FAM-1"
        self.item.revision = "A"
        self.item.data_source = DataSource.CAD
        self.item_repo = FakeMadeItemRepository([self.item])
        self.article_group_repo = FakeArticleGroupRepository()
        self.bought_item_repo = MadeBoughtItemRepo()
        self.source_item_repo = FakeSourceItemRepository()
        self.fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1)]
        )
        self.inspection_method_repo = FakeInspectionMethodRepository([make_inspection_method(id=1)])
        self.admin_settings_repo = MadeSettingsRepo()
        self.registry = FakePartNumberRegistry()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = CreateMadeItemRevision(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
        )

    def _cmd(self, **item_kwargs) -> CreateMadeItemRevisionCommand:
        defaults = dict(article_name="Bracket")
        defaults.update(item_kwargs)
        return CreateMadeItemRevisionCommand(
            predecessor_status="replaced", item=MadeItemRevisionItemCommand(**defaults)
        )

    async def test_human_actor_on_cad_family_rejected(self):
        actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        with pytest.raises(MadeItemRevisionManagedByPdmError):
            await self.use_case.execute(actor=actor, item_id=1, cmd=self._cmd())

    async def test_system_user_on_cad_family_allowed(self):
        system_actor = make_user(
            id=2, username="system", permissions=[Permission.WRITE_MADE_ITEMS], is_systemuser=True
        )
        result = await self.use_case.execute(actor=system_actor, item_id=1, cmd=self._cmd())
        assert result.part_number == "FAM-1"
        assert result.revision == "B"


# ── MergeMadeItem ─────────────────────────────────────────────────────


class TestMergeMadeItemPdmEnforcement:
    def setup_method(self):
        self.source = make_made_item(id=1, article_name="Source")
        self.target = make_made_item(id=2, article_name="Target")
        self.item_repo = FakeMadeItemRepository([self.source, self.target])
        self.file_repo = FakeMadeItemFileRepository()
        self.uow = FakeUnitOfWork()
        self.registry = FakePartNumberRegistry()
        self.actor = make_user(permissions=[Permission.DELETE_MADE_ITEMS])
        self.system_actor = make_user(
            id=2,
            username="system",
            permissions=[Permission.DELETE_MADE_ITEMS],
            is_systemuser=True,
        )

    def _use_case(self, admin_settings_repo: MadeSettingsRepo) -> MergeMadeItem:
        return MergeMadeItem(
            self.item_repo,
            self.file_repo,
            self.uow,
            PdmCadSource(admin_settings_repo),
            part_number_registry=self.registry,
            picture_repo=FakeItemPictureRepository(),
            item_usages=FakeMadeItemUsages(),
        )

    async def test_enforcement_off_allows_merging_cad_source(self):
        self.source.data_source = DataSource.CAD
        use_case = self._use_case(MadeSettingsRepo())
        result = await use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
        )
        assert result.id == 2

    async def test_enforcement_on_web_source_allowed(self):
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
        )
        assert result.id == 2

    async def test_enforcement_on_cad_source_rejected(self):
        self.source.data_source = DataSource.CAD
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError):
            await use_case.execute(
                actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
            )

    async def test_system_user_bypasses_enforcement(self):
        self.source.data_source = DataSource.CAD
        settings = MadeSettingsRepo(pdm=make_made_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.system_actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
        )
        assert result.id == 2


# ── MergeBoughtItem ───────────────────────────────────────────────────


class TestMergeBoughtItemPdmEnforcement:
    def setup_method(self):
        self.source = make_bought_item(id=1, article_name="Source")
        self.target = make_bought_item(id=2, article_name="Target")
        self.item_repo = FakeBoughtItemRepository([self.source, self.target])
        self.file_repo = FakeBoughtItemFileRepository()
        self.uow = FakeUnitOfWork()
        self.registry = FakePartNumberRegistry()
        self.actor = make_user(permissions=[Permission.DELETE_BOUGHT_ITEMS])
        self.system_actor = make_user(
            id=2,
            username="system",
            permissions=[Permission.DELETE_BOUGHT_ITEMS],
            is_systemuser=True,
        )

    def _use_case(self, admin_settings_repo: BoughtSettingsRepo) -> MergeBoughtItem:
        return MergeBoughtItem(
            self.item_repo,
            self.file_repo,
            self.uow,
            PdmCadSource(admin_settings_repo),
            part_number_registry=self.registry,
            picture_repo=FakeItemPictureRepository(),
            item_usages=FakeBoughtItemUsages(),
        )

    async def test_enforcement_off_allows_merging_cad_source(self):
        self.source.data_source = DataSource.CAD
        use_case = self._use_case(BoughtSettingsRepo())
        result = await use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeBoughtItemCommand(target_id=2)
        )
        assert result.id == 2

    async def test_enforcement_on_web_source_allowed(self):
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeBoughtItemCommand(target_id=2)
        )
        assert result.id == 2

    async def test_enforcement_on_cad_source_rejected(self):
        self.source.data_source = DataSource.CAD
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        with pytest.raises(PdmOwnedFieldReadOnlyError):
            await use_case.execute(
                actor=self.actor, source_id=1, cmd=MergeBoughtItemCommand(target_id=2)
            )

    async def test_system_user_bypasses_enforcement(self):
        self.source.data_source = DataSource.CAD
        settings = BoughtSettingsRepo(pdm=make_bought_pdm_settings(enabled=True))
        use_case = self._use_case(settings)
        result = await use_case.execute(
            actor=self.system_actor, source_id=1, cmd=MergeBoughtItemCommand(target_id=2)
        )
        assert result.id == 2
