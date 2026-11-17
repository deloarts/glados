"""
Unit tests for RegroupMadeItemProcesses.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import RegroupMadeItemProcessesCommand
from src.modules.catalogue.application.use_cases.made_item.regroup_made_item_processes import (
    RegroupMadeItemProcesses,
)
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_process
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestRegroupMadeItemProcesses:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=0))
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=1))
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=2))
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.use_case = RegroupMadeItemProcesses(
            self.item_repo, self.admin_settings_repo, uow=FakeUnitOfWork()
        )

    async def test_regroups_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=RegroupMadeItemProcessesCommand(groups=[[1, 2], [3]]),
        )
        assert {p.id: p.group_index for p in result} == {1: 0, 2: 0, 3: 1}

    async def test_missing_item_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=999,
                cmd=RegroupMadeItemProcessesCommand(groups=[[1, 2, 3]]),
            )

    async def test_unprivileged_cannot_regroup(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor=actor,
                made_item_id=1,
                cmd=RegroupMadeItemProcessesCommand(groups=[[1, 2, 3]]),
            )

    async def test_missing_process_in_groups_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=RegroupMadeItemProcessesCommand(groups=[[1, 2]]),
            )

    async def test_non_contiguous_group_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=RegroupMadeItemProcessesCommand(groups=[[1, 3], [2]]),
            )

    async def test_unknown_process_id_raises(self):
        with pytest.raises(MadeItemProcessGroupingInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=RegroupMadeItemProcessesCommand(groups=[[1, 2, 999]]),
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
                made_item_id=1,
                cmd=RegroupMadeItemProcessesCommand(groups=[[1, 2], [3]]),
            )
