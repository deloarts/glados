"""
Unit tests for MergeMadeItem.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import MergeMadeItemCommand
from src.modules.catalogue.application.use_cases.made_item.merge_made_item import MergeMadeItem
from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeMadeItemUsages
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.item_picture_fakes import FakeItemPictureRepository
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeMadeItemFileRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository
from tests.unit.made_item.fakes import FakePartNumberRegistry


class TestMergeMadeItem:
    def setup_method(self):
        self.source = make_made_item(id=1, article_name="Source")
        self.target = make_made_item(id=2, article_name="Target")
        self.item_repo = FakeMadeItemRepository([self.source, self.target])
        self.file_repo = FakeMadeItemFileRepository()
        self.uow = FakeUnitOfWork()
        self.registry = FakePartNumberRegistry()
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.DELETE_MADE_ITEMS])
        self.use_case = MergeMadeItem(
            self.item_repo,
            self.file_repo,
            self.uow,
            PdmCadSource(self.admin_settings_repo),
            part_number_registry=self.registry,
            picture_repo=FakeItemPictureRepository(),
            item_usages=FakeMadeItemUsages(),
        )

    async def test_merges_and_deletes_source(self):
        result = await self.use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
        )
        assert result.id == 2
        assert await self.item_repo.get_by_id(1) is None
        assert self.uow.committed is True
        assert (1, 2) in self.item_repo.merged_article_groups

    async def test_missing_source_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor, source_id=999, cmd=MergeMadeItemCommand(target_id=2)
            )

    async def test_same_source_and_target_raises(self):
        with pytest.raises(InvalidInputError):
            await self.use_case.execute(
                actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=1)
            )

    async def test_releases_source_part_number_if_unused(self):
        self.source.part_number = "PN-1"
        await self.registry.claim("PN-1", "made")

        await self.use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
        )

        assert self.registry.entries.get("PN-1") is None

    @pytest.mark.parametrize(
        ("status", "archived"),
        [
            (MadeItemCatalogueStatus.INACTIVE, False),
            (MadeItemCatalogueStatus.REPLACED, False),
            (MadeItemCatalogueStatus.ACTIVE, True),
        ],
    )
    async def test_refuses_a_target_that_is_not_active_or_is_archived(
        self, status: MadeItemCatalogueStatus, archived: bool
    ):
        self.target.status = status
        self.target.archived = archived

        with pytest.raises(MadeItemInactiveError):
            await self.use_case.execute(
                actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
            )

        assert await self.item_repo.get_by_id(1) is not None
        assert self.uow.committed is False

    async def test_a_target_the_source_had_replaced_becomes_active_again(self):
        self.target.status = MadeItemCatalogueStatus.REPLACED
        self.target.successor_item_id = 1

        result = await self.use_case.execute(
            actor=self.actor, source_id=1, cmd=MergeMadeItemCommand(target_id=2)
        )

        assert (result.status, result.successor_item_id) == ("active", None)
        assert any("active again" in line for line in result.changes)
