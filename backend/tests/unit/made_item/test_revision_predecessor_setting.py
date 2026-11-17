"""
The status a new revision gives its predecessor: the web follows the admin
setting and takes the request's value only while the setting is "ask", PDM
ingest passes its own setting, and the predecessor names the new revision as
successor only when it ends replaced. No database, no HTTP.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionItemCommand
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_fabrication_method
from tests.unit.made_item._helpers import make_inspection_method
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


def _settings(predecessor_status_web: str) -> AdminMadeItemSettings:
    return AdminMadeItemSettings(
        id=1,
        item_number_format="MADE-{year}-{seq:04d}",
        lot_number_format="LOT-{year}-{seq:04d}",
        part_number_auto=False,
        part_number_editable=True,
        revision_start="0",
        revision_separator=":",
        revision_skip_ambiguous_letters=False,
        revision_only_newest_editable=True,
        revision_predecessor_status_web=predecessor_status_web,
        revision_predecessor_status_pdm="replaced",
        revision_field_policy=default_policy(),
        web_creation_allowed=True,
        pdm_part_number_pattern="",
    )


class TestPredecessorStatus:
    def setup_method(self) -> None:
        self.item = make_made_item(id=1, part_number="FAM-1", revision="A")
        self.item_repo = FakeMadeItemRepository([self.item])
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.system_actor = make_user(id=2, username="system", is_systemuser=True)

    def _use_case(self, predecessor_status_web: str) -> CreateMadeItemRevision:
        return CreateMadeItemRevision(
            self.item_repo,
            FakeArticleGroupRepository(),
            FakeBoughtItemRepository(),
            FakeSourceItemRepository(),
            FakeFabricationMethodRepository([make_fabrication_method(id=1)]),
            FakeInspectionMethodRepository([make_inspection_method(id=1)]),
            FakeAdminSettingsRepository(made_items=_settings(predecessor_status_web)),
            part_number_registry=FakePartNumberRegistry(),
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            customer_repo=FakeCustomerRepository(),
        )

    @staticmethod
    def _cmd(predecessor_status: str) -> CreateMadeItemRevisionCommand:
        return CreateMadeItemRevisionCommand(
            predecessor_status=predecessor_status,
            item=MadeItemRevisionItemCommand(article_name="Bracket"),
        )

    @pytest.mark.parametrize(
        ("configured", "requested"),
        [("inactive", "replaced"), ("active", "replaced"), ("replaced", "inactive")],
    )
    async def test_a_fixed_web_setting_decides_over_the_request(self, configured, requested):
        result = await self._use_case(configured).execute(
            actor=self.actor, item_id=1, cmd=self._cmd(requested)
        )

        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == configured
        expected_successor = result.id if configured == "replaced" else None
        assert predecessor.successor_item_id == expected_successor

    @pytest.mark.parametrize("requested", ["replaced", "inactive", "active"])
    async def test_ask_takes_the_request(self, requested):
        await self._use_case("ask").execute(actor=self.actor, item_id=1, cmd=self._cmd(requested))

        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == requested

    async def test_pdm_ingest_keeps_the_status_it_passes(self):
        self.item.data_source = DataSource.CAD

        await self._use_case("inactive").execute(
            actor=self.system_actor, item_id=1, cmd=self._cmd("replaced")
        )

        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == "replaced"

    async def test_a_predecessor_that_is_not_replaced_drops_a_stale_successor(self):
        self.item.successor_item_id = 999

        await self._use_case("inactive").execute(
            actor=self.actor, item_id=1, cmd=self._cmd("inactive")
        )

        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == "inactive"
        assert predecessor.successor_item_id is None
        assert "Successor item #999 cleared" in predecessor.changes[-1]
