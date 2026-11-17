"""
Unit tests for the customer data of a customer item: the completeness rule,
the customer lookup of CreateMadeItem, UpdateMadeItem and
CreateMadeItemRevision, and the default revision policy of the three fields.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionItemCommand
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemCommand
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.update_made_item import UpdateMadeItem
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.errors import MadeItemCustomerDataInvalidError
from src.modules.catalogue.domain.errors import MadeItemFieldRequiresRevisionError
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeArticleGroupRepository
from tests.unit.made_item.fakes import FakeBoughtItemRepository
from tests.unit.made_item.fakes import FakeCustomerRepository
from tests.unit.made_item.fakes import FakeFabricationMethodRepository
from tests.unit.made_item.fakes import FakeInspectionMethodRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository
from tests.unit.made_item.fakes import FakePartNumberRegistry
from tests.unit.made_item.fakes import FakeSourceItemRepository

_CUSTOMER_FIELDS = ("customer_id", "customer_part_number", "customer_revision")


def _customer(id: int, *, archived: bool = False) -> Customer:
    return Customer(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        archived=archived,
        name=f"Customer {id}",
        legal_name=None,
        vat_id=None,
        level=CustomerLevel.B,
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        creator_id=1,
    )


class TestCompletenessRule:
    def test_no_customer_and_no_data_passes(self):
        MadeItemCatalogueRules.assert_customer_data_complete(None, None, None)

    def test_customer_with_part_number_passes_without_revision(self):
        MadeItemCatalogueRules.assert_customer_data_complete(7, "C-100", None)

    def test_customer_without_part_number_is_refused(self):
        with pytest.raises(MadeItemCustomerDataInvalidError):
            MadeItemCatalogueRules.assert_customer_data_complete(7, None, "B")

    @pytest.mark.parametrize(("part_number", "revision"), [("C-100", None), (None, "B")])
    def test_customer_data_without_customer_is_refused(self, part_number, revision):
        with pytest.raises(MadeItemCustomerDataInvalidError):
            MadeItemCatalogueRules.assert_customer_data_complete(None, part_number, revision)


class TestDefaultPolicy:
    def test_customer_fields_need_a_revision_on_the_web_and_update_in_place_from_pdm(self):
        policy = {p.field: p for p in default_policy()}
        for field in _CUSTOMER_FIELDS:
            assert policy[field].web_requires_revision is True
            assert policy[field].pdm_update_in_place is True


def _create_use_case(customers: list[Customer]) -> CreateMadeItem:
    return CreateMadeItem(
        FakeMadeItemRepository(),
        FakeArticleGroupRepository(),
        FakeBoughtItemRepository(),
        FakeSourceItemRepository(),
        FakeFabricationMethodRepository(),
        FakeInspectionMethodRepository(),
        FakeAdminSettingsRepository(),
        customer_repo=FakeCustomerRepository(customers),
        part_number_registry=FakePartNumberRegistry(),
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
        cad_source=PdmCadSource(FakeAdminSettingsRepository()),
    )


def _create_cmd(**kwargs) -> CreateMadeItemCommand:
    return CreateMadeItemCommand(revision="A", article_name="Housing", **kwargs)


class TestCreate:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])

    async def test_stores_the_customer_data(self):
        use_case = _create_use_case([_customer(7)])

        result = await use_case.execute(
            self.actor,
            _create_cmd(customer_id=7, customer_part_number="C-100", customer_revision="B"),
        )

        assert result.customer_id == 7
        assert result.customer_part_number == "C-100"
        assert result.customer_revision == "B"

    async def test_accepts_an_archived_customer(self):
        use_case = _create_use_case([_customer(7, archived=True)])

        result = await use_case.execute(
            self.actor, _create_cmd(customer_id=7, customer_part_number="C-100")
        )

        assert result.customer_id == 7

    async def test_unknown_customer_is_refused(self):
        use_case = _create_use_case([])

        with pytest.raises(CustomerNotFoundError):
            await use_case.execute(
                self.actor, _create_cmd(customer_id=7, customer_part_number="C-100")
            )

    async def test_incomplete_customer_data_is_refused(self):
        use_case = _create_use_case([_customer(7)])

        with pytest.raises(MadeItemCustomerDataInvalidError):
            await use_case.execute(self.actor, _create_cmd(customer_id=7))

    async def test_the_system_user_stores_incomplete_data_as_received(self):
        use_case = _create_use_case([])
        system_user = make_user(is_systemuser=True, permissions=[Permission.WRITE_MADE_ITEMS])

        result = await use_case.execute(system_user, _create_cmd(customer_revision="B"))

        assert result.customer_id is None
        assert result.customer_revision == "B"


class TestUpdate:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])

    def _use_case(self, items, customers: list[Customer]) -> UpdateMadeItem:
        return UpdateMadeItem(
            FakeMadeItemRepository(items),
            FakeArticleGroupRepository(),
            FakeBoughtItemRepository(),
            FakeSourceItemRepository(),
            FakeAdminSettingsRepository(),
            customer_repo=FakeCustomerRepository(customers),
            part_number_registry=FakePartNumberRegistry(),
            uow=FakeUnitOfWork(),
            cad_source=PdmCadSource(FakeAdminSettingsRepository()),
        )

    def _cmd(self, item, **changes) -> UpdateMadeItemCommand:
        fields = {
            f: getattr(item, f)
            for f in UpdateMadeItemCommand.model_fields
            if f != "expected_edit_version"
        }
        fields.update(changes)
        return UpdateMadeItemCommand(**fields)

    async def test_web_item_changes_customer_data_only_through_a_new_revision(self):
        item = make_made_item(id=1, data_source=DataSource.WEB)
        use_case = self._use_case([item], [_customer(7)])

        with pytest.raises(MadeItemFieldRequiresRevisionError) as exc_info:
            await use_case.execute(
                self.actor, 1, self._cmd(item, customer_id=7, customer_part_number="C-100")
            )

        assert "customer_id" in str(exc_info.value)

    async def test_cad_item_stores_a_complete_change(self):
        item = make_made_item(id=1, data_source=DataSource.CAD)
        use_case = self._use_case([item], [_customer(7)])

        result = await use_case.execute(
            self.actor, 1, self._cmd(item, customer_id=7, customer_part_number="C-100")
        )

        assert result.customer_id == 7
        assert result.customer_part_number == "C-100"

    async def test_incomplete_data_from_pdm_does_not_block_other_edits(self):
        item = make_made_item(id=1, data_source=DataSource.CAD)
        item.customer_revision = "B"
        use_case = self._use_case([item], [])

        result = await use_case.execute(self.actor, 1, self._cmd(item, note="checked"))

        assert result.note == "checked"
        assert result.customer_revision == "B"

    async def test_an_incomplete_change_is_refused(self):
        item = make_made_item(id=1, data_source=DataSource.CAD)
        use_case = self._use_case([item], [_customer(7)])

        with pytest.raises(MadeItemCustomerDataInvalidError):
            await use_case.execute(self.actor, 1, self._cmd(item, customer_id=7))


class TestRevision:
    async def test_a_new_revision_carries_new_customer_data(self):
        actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        item = make_made_item(id=1, part_number="FAB-0001", revision="A")
        item_repo = FakeMadeItemRepository([item])
        use_case = CreateMadeItemRevision(
            item_repo,
            FakeArticleGroupRepository(),
            FakeBoughtItemRepository(),
            FakeSourceItemRepository(),
            FakeFabricationMethodRepository(),
            FakeInspectionMethodRepository(),
            FakeAdminSettingsRepository(),
            customer_repo=FakeCustomerRepository([_customer(7)]),
            part_number_registry=FakePartNumberRegistry(),
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
        )

        result = await use_case.execute(
            actor,
            1,
            CreateMadeItemRevisionCommand(
                predecessor_status="replaced",
                item=MadeItemRevisionItemCommand(
                    article_name=item.article_name,
                    customer_id=7,
                    customer_part_number="C-100",
                    customer_revision="C",
                ),
            ),
        )

        assert result.revision == "B"
        assert result.customer_id == 7
        assert result.customer_revision == "C"
