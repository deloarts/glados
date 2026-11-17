"""
Made-item file use cases: newest-only gate. tests/unit/test_item_file_behaviour.py
stays kind-agnostic (bought/made/source built identically), so it constructs
Upload/Update/DeleteMadeItemFile without a made_item_repo/admin_settings_repo
(both optional there, defaulting to a no-op gate; see
upload_made_item_file.py's docstring comment). The real gate, wired exactly
as deps/items.py wires it, is covered here instead.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.made_item_file_dto import UpdateMadeItemFileCommand
from src.modules.catalogue.application.use_cases.made_item.delete_made_item_file import (
    DeleteMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.update_made_item_file import (
    UpdateMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeMadeItemFileRepository
from tests.unit.made_item.fakes import FakeMadeItemFileStorage
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestMadeItemFileNewestOnlyGate:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item.part_number = "FAM-1"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-1"
        newest.revision = "B"
        self.item_repo = FakeMadeItemRepository([self.item, newest])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])

    async def test_upload_blocked_when_not_newest(self):
        use_case = UploadMadeItemFile(
            self.item_repo,
            FakeMadeItemFileRepository(),
            FakeMadeItemFileStorage(),
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(MadeItemNotNewestRevisionError):
            await use_case.execute(
                actor=self.actor,
                item_id=1,
                data=b"x",
                file_name="a.pdf",
                content_type="application/pdf",
                category=MadeItemFileCategory.PDF,
            )

    async def test_update_blocked_when_not_newest(self):
        file = MadeItemFile(
            id=1,
            created=datetime.now(UTC),
            made_item_id=1,
            category=MadeItemFileCategory.PDF,
            file_name="a.pdf",
            stored_name="a.pdf",
            storage_path="made_items/catalogue/1/pdf/a.pdf",
            sha256="x",
            size_bytes=1,
            mime_type="application/pdf",
            uploaded_by_user_id=1,
        )
        use_case = UpdateMadeItemFile(
            FakeMadeItemFileRepository([file]),
            None,
            self.item_repo,
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(MadeItemNotNewestRevisionError):
            await use_case.execute(
                actor=self.actor, file_id=1, command=UpdateMadeItemFileCommand(file_name="b.pdf")
            )

    async def test_delete_blocked_when_not_newest(self):
        file = MadeItemFile(
            id=1,
            created=datetime.now(UTC),
            made_item_id=1,
            category=MadeItemFileCategory.PDF,
            file_name="a.pdf",
            stored_name="a.pdf",
            storage_path="made_items/catalogue/1/pdf/a.pdf",
            sha256="x",
            size_bytes=1,
            mime_type="application/pdf",
            uploaded_by_user_id=1,
        )
        use_case = DeleteMadeItemFile(
            FakeMadeItemFileRepository([file]),
            None,
            self.item_repo,
            self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(MadeItemNotNewestRevisionError):
            await use_case.execute(actor=self.actor, file_id=1)
