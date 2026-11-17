"""
Unit tests for DeleteMadeItemProcess.
"""

import pytest

from src.modules.catalogue.application.use_cases.made_item.delete_made_item_process import (
    DeleteMadeItemProcess,
)
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemProcessNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_process
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestDeleteMadeItemProcess:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.uow = FakeUnitOfWork()
        self.use_case = DeleteMadeItemProcess(self.item_repo, self.admin_settings_repo, self.uow)

    async def test_delete_renormalizes_groups(self):
        await self.item_repo.save_process(
            make_process(id=0, made_item_id=1, position=0, group_index=0)
        )
        await self.item_repo.save_process(
            make_process(id=0, made_item_id=1, position=1, group_index=0)
        )
        await self.item_repo.save_process(
            make_process(id=0, made_item_id=1, position=2, group_index=1)
        )

        # Deleting the middle process of group 0 leaves its sibling (id 1)
        # and the standalone process (id 3) as two separate groups.
        await self.use_case.execute(actor=self.actor, item_id=1, process_id=2)

        remaining = await self.item_repo.get_processes(1)
        assert {p.id: p.group_index for p in remaining} == {1: 0, 3: 1}
        assert {p.id: p.position for p in remaining} == {1: 0, 3: 1}
        assert self.uow.committed

    async def test_deleting_a_process_belonging_to_another_item_raises(self):
        other_item = make_made_item(id=2)
        await self.item_repo.save(other_item)
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=0))
        await self.item_repo.save_process(make_process(id=0, made_item_id=2, position=0))

        with pytest.raises(MadeItemProcessNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=1, process_id=2)

    async def test_blocked_when_item_is_not_the_newest_revision(self):
        self.item.part_number = "FAM-1"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-1"
        newest.revision = "B"
        self.item_repo._items[2] = newest
        await self.item_repo.save_process(make_process(id=0, made_item_id=1, position=0))

        with pytest.raises(MadeItemNotNewestRevisionError):
            await self.use_case.execute(actor=self.actor, item_id=1, process_id=1)
