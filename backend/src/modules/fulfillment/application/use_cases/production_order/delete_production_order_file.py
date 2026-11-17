"""Use case for deleting an inspection evidence file attached to a production order."""

from src.modules.fulfillment.domain.errors import ProductionOrderFileNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteProductionOrderFile:
    def __init__(
        self,
        file_repo: IProductionOrderFileRepository,
        storage: IStoragePort | None,
        *,
        order_repo: IProductionOrderRepository,
        uow: IUnitOfWork,
    ) -> None:
        """The order repository locks the file's production order, so a
        completion that checks for evidence under that lock sees the file
        either still there or already gone, never a delete in flight."""
        self._file_repo = file_repo
        self._orders = order_repo
        self._storage = storage
        self._uow = uow

    async def execute(self, actor: User, file_id: int) -> None:
        if not actor.has_permission(Permission.WRITE_INSPECTIONS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot delete inspection evidence files."
            )

        file = found_or_raise(
            await self._file_repo.get_by_id(file_id),
            ProductionOrderFileNotFoundError,
            f"File #{file_id} not found.",
        )
        await self._orders.lock_for_update([file.production_order_id])

        await self._file_repo.delete(file)
        await self._uow.commit()

        # The blob goes only once the row deletion has committed, so a failed
        # commit leaves the row with its file intact. A failed blob delete
        # leaves an orphan, which is logged and not raised.
        if self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage,
                file.storage_path,
                context=f"deleting production order file #{file_id}",
            )
        log.info("Production order file #%s (%r) deleted.", file_id, file.file_name)
