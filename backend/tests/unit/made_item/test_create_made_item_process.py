"""
Unit tests for CreateMadeItemProcess.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.application.use_cases.made_item.create_made_item_process import (
    CreateMadeItemProcess,
)
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_fabrication_method
from tests.unit.made_item._helpers import make_inspection_method
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeFabricationMethodRepository
from tests.unit.made_item.fakes import FakeInspectionMethodRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestCreateMadeItemProcess:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        self.fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1)]
        )
        self.inspection_method_repo = FakeInspectionMethodRepository([make_inspection_method(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.use_case = CreateMadeItemProcess(
            self.item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )

    async def test_appends_at_end(self):
        first = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
        )
        second = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
        )
        assert first.position == 0
        assert second.position == 1

    async def test_appends_as_own_new_group(self):
        first = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
        )
        second = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
        )
        assert first.group_index == 0
        assert second.group_index == 1

    async def test_group_index_on_request_is_ignored(self):
        # A single-step add is never grouped with an existing step, even if
        # the request supplies a group_index hint, only the regroup
        # endpoint groups existing processes together.
        first = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
        )
        second = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(fabrication_method_id=1, group_index=0),
        )
        assert second.group_index == first.group_index + 1

    async def test_missing_item_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=999,
                cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
            )

    async def test_missing_fabrication_method_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=CreateMadeItemProcessCommand(fabrication_method_id=999),
            )

    async def test_archived_fabrication_method_raises(self):
        fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1), make_fabrication_method(id=2, archived=True)]
        )
        use_case = CreateMadeItemProcess(
            self.item_repo,
            fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(FabricationMethodArchivedError):
            await use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=CreateMadeItemProcessCommand(fabrication_method_id=2),
            )

    async def test_inspection_process_needs_no_fabrication_method(self):
        result = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=CreateMadeItemProcessCommand(
                role=StepRole.INSPECTION.value,
                inspection_method_id=1,
            ),
        )
        assert result.role == "inspection"
        assert result.inspection_method_id == 1
        assert result.fabrication_method_id is None

    async def test_missing_inspection_method_raises(self):
        with pytest.raises(InspectionMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=CreateMadeItemProcessCommand(
                    role=StepRole.INSPECTION.value, inspection_method_id=999
                ),
            )

    async def test_archived_inspection_method_raises(self):
        inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1), make_inspection_method(id=2, archived=True)]
        )
        use_case = CreateMadeItemProcess(
            self.item_repo,
            self.fabrication_method_repo,
            inspection_method_repo,
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(InspectionMethodArchivedError):
            await use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=CreateMadeItemProcessCommand(
                    role=StepRole.INSPECTION.value, inspection_method_id=2
                ),
            )

    async def test_blocked_when_item_is_not_the_newest_revision(self):
        # Process/file mutation use cases apply the newest-only rule
        # unconditionally (no status exemption; they never touch status).
        self.item.part_number = "FAM-1"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-1"
        newest.revision = "B"
        self.item_repo._items[2] = newest

        with pytest.raises(MadeItemNotNewestRevisionError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=CreateMadeItemProcessCommand(fabrication_method_id=1),
            )
