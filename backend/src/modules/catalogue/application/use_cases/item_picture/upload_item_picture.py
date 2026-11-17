"""
A person's photo of the real object, stored as the item's PICTURE source.
It replaces only the previous photo, never the Data Portal picture or the
CAD rendering, and as the highest-ranked source it is always the picture
shown. The thumbnail is derived from it (ItemPictureStore).
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

from src.modules.catalogue.application.dto.item_picture_dto import ItemPictureResult
from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureItemRepo
from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureKind
from src.modules.catalogue.domain.errors import ItemPictureInvalidTypeError
from src.modules.catalogue.domain.errors import ItemPictureTooLargeError
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.platform.application.services.file_attachments.config import IMAGE_CONTENT_TYPES
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

MAX_PICTURE_BYTES = 10 * MiB

# A rule beyond the write permission that needs the loaded item, such as a
# made item's newest-revision rule; raises when the item may not change.
EditableCheck = Callable[[Any], Awaitable[None]]


class UploadItemPicture:
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

    async def execute(
        self, actor: User, item_id: int, data: bytes, file_name: str, content_type: str
    ) -> ItemPictureResult:
        self._kind.write_rule(actor)
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")
        item = await self._items.get_by_id(item_id)
        if not item:
            raise self._kind.not_found(item_id)
        if self._editable_check is not None:
            await self._editable_check(item)
        if len(data) > MAX_PICTURE_BYTES:
            raise ItemPictureTooLargeError(
                f"Pictures must be ≤ {MAX_PICTURE_BYTES // MiB} MB (got {len(data)} bytes)."
            )
        if content_type not in IMAGE_CONTENT_TYPES:
            raise ItemPictureInvalidTypeError(
                f"Expected an image (JPEG/PNG/WebP) for a picture, got {content_type!r}."
            )

        # Nothing has been written yet. Ending the read transaction hands the
        # connection back to the pool for the image processing and upload.
        await self._uow.commit()

        store = ItemPictureStore(self._pictures, self._storage)
        staged = await store.stage(
            self._kind.kind, item_id, ItemPictureSource.PICTURE, data, file_name, actor.id
        )
        try:
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            await store.discard(staged)
            raise
        await store.finish(staged)

        log.info(
            f"Picture uploaded for {self._kind.item_label} #%s: %r by user #%s.",
            item_id,
            file_name,
            actor.id,
        )
        return ItemPictureResult.of(staged.picture, in_use=True)
