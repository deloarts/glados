"""
Deletes a file attached to a made item, checking the item's edit gate before
removing the file record and its storage object.
"""

from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.application.use_cases.made_item._file_kind import MADE_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_file_repository import (
    IMadeItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.file_attachments.base import DeleteItemFileBase
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteMadeItemFile(DeleteItemFileBase[MadeItemFile]):
    _kind = MADE_ITEM_FILE_KIND

    def __init__(
        self,
        file_repo: IMadeItemFileRepository,
        storage: IStoragePort | None,
        made_item_repo: IMadeItemRepository | None = None,
        admin_settings_repo: ICatalogueSettingsRepository | None = None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(file_repo, storage, uow=uow)
        # Both optional (deps/items.py always supplies both): keeps this
        # constructor call-compatible with tests/unit/
        # test_item_file_behaviour.py's kind-agnostic characterisation
        # suite, which builds every *ItemFile use case identically across
        # bought/made/source and predates the unified file-deletion use
        # case rewrite.
        self._made_item_repo = made_item_repo
        self._admin_settings = admin_settings_repo

    async def _assert_editable(self, file: MadeItemFile) -> None:
        if self._made_item_repo is None or self._admin_settings is None:
            return
        item = found_or_raise(
            await self._made_item_repo.get_by_id(file.made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{file.made_item_id} not found.",
        )
        await assert_made_item_editable(item, self._made_item_repo, self._admin_settings)
