"""Byte-serves inspection evidence files for production orders. Unlike its five
siblings (bought/made/source item, product, order), this family's list route is
gated on write:inspections rather than login-only, so this use case re-checks
the same permission GetProductionOrderFiles does, before touching storage.
"""

from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.errors import ProductionOrderFileNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.services.content_types import content_type_for
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DownloadProductionOrderFile:
    def __init__(
        self,
        file_repo: IProductionOrderFileRepository,
        storage: IStoragePort | None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(
        self, actor: User, order_id: int, file_id: int
    ) -> tuple[ProductionOrderFile, bytes, str]:
        if not actor.has_permission(Permission.WRITE_INSPECTIONS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot download inspection evidence files."
            )

        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")

        file = await self._file_repo.get_by_id(file_id)
        if not file or file.production_order_id != order_id:
            # A file id that exists but belongs to another parent 404s,
            # never 403s, because there is no cross-parent existence oracle.
            raise ProductionOrderFileNotFoundError(f"File #{file_id} not found.")

        # Nothing has been written. Ending the read transaction hands the
        # connection back to the pool for the storage download.
        if self._uow is not None:
            await self._uow.commit()

        # The type follows the stored extension rather than what storage
        # recorded, so it never repeats a type the uploading client claimed.
        data, _ = await self._storage.download(file.storage_path)
        return file, data, content_type_for(file.storage_path)
