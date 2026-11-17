"""
Metadata-only update (file_name). Replacing file bytes requires DELETE + POST.
"""

from src.modules.fulfillment.application.dto.production_order_file_dto import (
    ProductionOrderFileResult,
)
from src.modules.fulfillment.application.dto.production_order_file_dto import (
    UpdateProductionOrderFileCommand,
)
from src.modules.fulfillment.domain.errors import ProductionOrderFileNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateProductionOrderFile:
    def __init__(
        self,
        file_repo: IProductionOrderFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(
        self, actor: User, file_id: int, command: UpdateProductionOrderFileCommand
    ) -> ProductionOrderFileResult:
        if not actor.has_permission(Permission.WRITE_INSPECTIONS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot rename inspection evidence files."
            )

        file = found_or_raise(
            await self._file_repo.get_by_id(file_id),
            ProductionOrderFileNotFoundError,
            f"File #{file_id} not found.",
        )

        file.file_name = command.file_name
        saved = await self._file_repo.save(file)
        await self._uow.commit()
        log.info("Production order file #%s renamed to %r.", file_id, command.file_name)

        url = (
            get_storage_url_best_effort(
                self._storage,
                saved.storage_path,
                context=f"production order file #{saved.id}",
                file_name=saved.file_name,
            )
            if self._storage is not None
            else None
        )

        return ProductionOrderFileResult(
            id=saved.id,
            public_id=saved.public_id,
            production_order_id=saved.production_order_id,
            file_name=saved.file_name,
            stored_name=saved.stored_name,
            mime_type=saved.mime_type,
            size_bytes=saved.size_bytes,
            storage_path=saved.storage_path,
            sha256=saved.sha256,
            category=saved.category,
            created=saved.created,
            uploaded_by_user_id=saved.uploaded_by_user_id,
            url=url,
        )
