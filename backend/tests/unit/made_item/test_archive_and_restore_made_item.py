"""
Unit tests for ArchiveMadeItem and RestoreMadeItem.
"""

import pytest

from src.modules.catalogue.application.use_cases.made_item.archive_made_item import ArchiveMadeItem
from src.modules.catalogue.application.use_cases.made_item.restore_made_item import RestoreMadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestArchiveMadeItem:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        self.actor = make_user(permissions=[Permission.DELETE_MADE_ITEMS])
        self.use_case = ArchiveMadeItem(self.item_repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, item_id=1)
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1)


class TestRestoreMadeItem:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.DELETE_MADE_ITEMS])

    async def test_restores_successfully(self):
        item = make_made_item(id=1, archived=True)
        repo = FakeMadeItemRepository([item])
        result = await RestoreMadeItem(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, item_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        item = make_made_item(id=1, archived=True)
        repo = FakeMadeItemRepository([item])
        use_case = RestoreMadeItem(repo, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, item_id=1)
        result = await use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is False

    async def test_not_found_raises(self):
        repo = FakeMadeItemRepository([])
        with pytest.raises(MadeItemNotFoundError):
            await RestoreMadeItem(repo, uow=FakeUnitOfWork()).execute(actor=self.actor, item_id=999)

    async def test_unprivileged_cannot_restore(self):
        item = make_made_item(id=1, archived=True)
        repo = FakeMadeItemRepository([item])
        actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreMadeItem(repo, uow=FakeUnitOfWork()).execute(actor=actor, item_id=1)
