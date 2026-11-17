"""
Deletes an item's photo (the PICTURE source). The Data Portal picture and
the CAD rendering belong to their writers and cannot be deleted here; with
the photo gone, the next of them is the picture shown.
"""

from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureItemRepo
from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureKind
from src.modules.catalogue.application.use_cases.item_picture.upload_item_picture import (
    EditableCheck,
)
from src.modules.catalogue.domain.errors import ItemPictureNotFoundError
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteItemPicture:
    def __init__(
        self,
        kind: PictureKind,
        item_repo: PictureItemRepo,
        picture_repo: IItemPictureRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
        editable_check: EditableCheck | None = None,
    ) -> None:
        self._kind = kind
        self._items = item_repo
        self._pictures = picture_repo
        self._storage = storage
        self._uow = uow
        self._editable_check = editable_check

    async def execute(self, actor: User, item_id: int) -> None:
        self._kind.write_rule(actor)
        item = await self._items.get_by_id(item_id)
        if not item:
            raise self._kind.not_found(item_id)
        if self._editable_check is not None:
            await self._editable_check(item)
        picture = await self._pictures.get_by_source(
            self._kind.kind, item_id, ItemPictureSource.PICTURE
        )
        if picture is None:
            raise ItemPictureNotFoundError(
                f"{self._kind.item_label.capitalize()} #{item_id} has no picture to delete."
            )

        await self._pictures.delete(picture)
        await self._uow.commit()

        # The blobs go only once the row deletion has committed, so a failed
        # commit leaves the picture intact. A failed blob delete leaves an
        # orphan, which is logged and not raised.
        if self._storage is not None:
            for path in picture.storage_paths():
                await delete_storage_object_best_effort(
                    self._storage, path, context=f"deleting item picture #{picture.id}"
                )
        log.info(f"Picture of {self._kind.item_label} #%s deleted by user #%s.", item_id, actor.id)
