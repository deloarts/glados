"""
Unit tests for UpdateMadeItemProcess.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemProcessCommand
from src.modules.catalogue.application.use_cases.made_item.update_made_item_process import (
    UpdateMadeItemProcess,
)
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.catalogue.domain.errors import MadeItemProcessNotFoundError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_fabrication_method
from tests.unit.made_item._helpers import make_inspection_method
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_process
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeFabricationMethodRepository
from tests.unit.made_item.fakes import FakeInspectionMethodRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestUpdateMadeItemProcess:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=0))
        self.fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1), make_fabrication_method(id=2, archived=True)]
        )
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1), make_inspection_method(id=2, archived=True)]
        )
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.use_case = UpdateMadeItemProcess(
            self.item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            item_id=1,
            process_id=1,
            cmd=UpdateMadeItemProcessCommand(fabrication_method_id=1, note="Updated"),
        )
        assert result.note == "Updated"

    async def test_missing_process_raises(self):
        with pytest.raises(MadeItemProcessNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                process_id=999,
                cmd=UpdateMadeItemProcessCommand(fabrication_method_id=1),
            )

    async def test_process_belonging_to_another_item_raises(self):
        other_item = make_made_item(id=2)
        await self.item_repo.save(other_item)
        await self.item_repo.save_process(make_process(id=0, made_item_id=2, position=0))
        with pytest.raises(MadeItemProcessNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                process_id=2,  # belongs to item #2, requested via item #1
                cmd=UpdateMadeItemProcessCommand(fabrication_method_id=1),
            )

    async def test_missing_fabrication_method_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                process_id=1,
                cmd=UpdateMadeItemProcessCommand(fabrication_method_id=999),
            )

    async def test_changing_to_archived_fabrication_method_raises(self):
        with pytest.raises(FabricationMethodArchivedError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                process_id=1,
                cmd=UpdateMadeItemProcessCommand(fabrication_method_id=2),
            )

    async def test_editing_unrelated_field_on_process_with_now_archived_method_succeeds(self):
        await self.item_repo.save_process(
            make_process(id=0, made_item_id=1, position=1, fabrication_method_id=2)
        )
        result = await self.use_case.execute(
            actor=self.actor,
            item_id=1,
            process_id=2,
            cmd=UpdateMadeItemProcessCommand(fabrication_method_id=2, note="still editable"),
        )
        assert result.note == "still editable"

    async def test_changing_role_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                process_id=1,
                cmd=UpdateMadeItemProcessCommand(
                    role=StepRole.INSPECTION.value,
                    fabrication_method_id=None,
                    inspection_method_id=1,
                ),
            )

    async def test_blocked_when_item_is_not_the_newest_revision(self):
        self.item.part_number = "FAM-1"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-1"
        newest.revision = "B"
        self.item_repo._items[2] = newest

        with pytest.raises(MadeItemNotNewestRevisionError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                process_id=1,
                cmd=UpdateMadeItemProcessCommand(fabrication_method_id=1, note="x"),
            )
