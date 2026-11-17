"""
Retrieves all uploaded files associated with a production order, resolving
storage URLs and filtering by category.
"""

from src.modules.fulfillment.application.dto.production_order_file_dto import (
    ProductionOrderFileResult,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.storage_port import IStoragePort


def _to_result(f: ProductionOrderFile, storage: IStoragePort | None) -> ProductionOrderFileResult:
    url = (
        get_storage_url_best_effort(
            storage,
            f.storage_path,
            context=f"production order file #{f.id}",
            file_name=f.file_name,
        )
        if storage is not None
        else None
    )
    return ProductionOrderFileResult(
        id=f.id,
        public_id=f.public_id,
        production_order_id=f.production_order_id,
        file_name=f.file_name,
        stored_name=f.stored_name,
        mime_type=f.mime_type,
        size_bytes=f.size_bytes,
        storage_path=f.storage_path,
        sha256=f.sha256,
        category=f.category,
        created=f.created,
        uploaded_by_user_id=f.uploaded_by_user_id,
        url=url,
    )


class GetProductionOrderFiles:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        file_repo: IProductionOrderFileRepository,
        storage: IStoragePort | None,
    ) -> None:
        self._orders = order_repo
        self._file_repo = file_repo
        self._storage = storage

    async def execute(self, actor: User, order_id: int) -> list[ProductionOrderFileResult]:
        if not actor.has_permission(Permission.WRITE_INSPECTIONS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot view inspection evidence files."
            )
        if not await self._orders.get_by_id(order_id):
            raise ProductionOrderNotFoundError(f"Production order #{order_id} not found.")
        files = await self._file_repo.get_by_item_id(order_id)
        return [_to_result(f, self._storage) for f in files]
