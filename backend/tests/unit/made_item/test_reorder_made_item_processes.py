"""
Unit tests for ReorderMadeItemProcesses.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import ReorderMadeItemProcessesCommand
from src.modules.catalogue.application.use_cases.made_item.reorder_made_item_processes import (
    ReorderMadeItemProcesses,
)
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemProcessReorderMismatchError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_process
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestReorderMadeItemProcesses:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=0))
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=1))
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.use_case = ReorderMadeItemProcesses(
            self.item_repo, self.admin_settings_repo, uow=FakeUnitOfWork()
        )

    async def test_reorders_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            made_item_id=1,
            cmd=ReorderMadeItemProcessesCommand(ordered_process_ids=[2, 1]),
        )
        assert [p.id for p in result] == [2, 1]
        assert result[0].position == 0
        assert result[1].position == 1

    async def test_mismatched_id_set_raises(self):
        with pytest.raises(MadeItemProcessReorderMismatchError):
            await self.use_case.execute(
                actor=self.actor,
                made_item_id=1,
                cmd=ReorderMadeItemProcessesCommand(ordered_process_ids=[1]),
            )

    async def test_reorder_preserves_adjacent_group(self):
        item = make_made_item(id=2)
        item_repo = FakeMadeItemRepository([item])
        await item_repo.save_process(make_process(id=0, made_item_id=2, position=0, group_index=0))
        await item_repo.save_process(make_process(id=0, made_item_id=2, position=1, group_index=0))
        await item_repo.save_process(make_process(id=0, made_item_id=2, position=2, group_index=1))
        use_case = ReorderMadeItemProcesses(
            item_repo, self.admin_settings_repo, uow=FakeUnitOfWork()
        )

        # ids 1,2 form group 0; id 3 is group 1. Swap the whole grouped pair
        # with the standalone process without tearing the pair apart.
        result = await use_case.execute(
            actor=self.actor,
            made_item_id=2,
            cmd=ReorderMadeItemProcessesCommand(ordered_process_ids=[3, 1, 2]),
        )
        assert {p.id: p.group_index for p in result} == {3: 0, 1: 1, 2: 1}

    async def test_reorder_splits_torn_group(self):
        item = make_made_item(id=2)
        item_repo = FakeMadeItemRepository([item])
        await item_repo.save_process(make_process(id=0, made_item_id=2, position=0, group_index=0))
        await item_repo.save_process(make_process(id=0, made_item_id=2, position=1, group_index=0))
        await item_repo.save_process(make_process(id=0, made_item_id=2, position=2, group_index=1))
        use_case = ReorderMadeItemProcesses(
            item_repo, self.admin_settings_repo, uow=FakeUnitOfWork()
        )

        # Dragging id 3 between the previously-grouped ids 1 and 2 tears
        # group 0 apart -> three separate groups.
        result = await use_case.execute(
            actor=self.actor,
            made_item_id=2,
            cmd=ReorderMadeItemProcessesCommand(ordered_process_ids=[1, 3, 2]),
        )
        assert {p.id: p.group_index for p in result} == {1: 0, 3: 1, 2: 2}

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
                cmd=ReorderMadeItemProcessesCommand(ordered_process_ids=[1, 2]),
            )
