"""
Deletes an order file record and its backing storage object (if storage is enabled) on a
best-effort basis. A picture of a delivery row may also be deleted by a receiver
(OrderRules.assert_can_delete_order_file), so the file is read before the permission is
checked; anyone else is refused before a missing file is reported.
"""

from src.modules.fulfillment.domain.errors import OrderFileNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.ports.outbound.repositories.order_file_repository import (
    IOrderFileRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteOrderFile:
    def __init__(
        self,
        file_repo: IOrderFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(self, actor: User, file_id: int) -> None:
        if not actor.has_permission(Permission.RECEIVE_DELIVERIES):
            OrderRules.assert_can_manage_files(actor)

        file = found_or_raise(
            await self._file_repo.get_by_id(file_id),
            OrderFileNotFoundError,
            f"Order file #{file_id} not found.",
        )
        OrderRules.assert_can_delete_order_file(actor, file.delivery_id)

        await self._file_repo.delete(file)
        await self._uow.commit()

        # The blob goes only once the row deletion has committed, so a failed
        # commit leaves the row with its file intact. A failed blob delete
        # leaves an orphan, which is logged and not raised.
        if self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage, file.storage_path, context=f"deleting order file #{file_id}"
            )
        log.info("Order file #%s (%r) deleted.", file_id, file.file_name)
