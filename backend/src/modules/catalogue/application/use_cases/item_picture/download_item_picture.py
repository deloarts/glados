"""
Serves one picture of an item: the one shown for it (pick_picture), or the
picture of one source when the detail page shows them all, as the image
or its thumbnail.
"""

from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureKind
from src.modules.catalogue.domain.errors import ItemPictureNotFoundError
from src.modules.catalogue.domain.policies.item_picture_selection import pick_picture
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DownloadItemPicture:
    def __init__(
        self,
        kind: PictureKind,
        picture_repo: IItemPictureRepository,
        storage: IStoragePort | None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._kind = kind
        self._pictures = picture_repo
        self._storage = storage
        self._uow = uow

    async def execute(
        self,
        item_id: int,
        variant: ItemPictureVariant,
        source: ItemPictureSource | None = None,
    ) -> tuple[bytes, str]:
        """Returns (bytes, content type). Raises ItemPictureNotFoundError
        when the item has no picture, or none of `source`."""
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")
        pictures = await self._pictures.get_by_item(self._kind.kind, item_id)
        if source is not None:
            pictures = [p for p in pictures if p.source is source]
        picture = pick_picture(pictures)
        blob = picture.blob(variant) if picture is not None else None
        if blob is None:
            wanted = f"{source.value} picture" if source is not None else "picture"
            raise ItemPictureNotFoundError(
                f"{self._kind.item_label.capitalize()} #{item_id} has no {wanted}."
            )

        # Nothing has been written. Ending the read transaction hands the
        # connection back to the pool for the storage download.
        if self._uow is not None:
            await self._uow.commit()

        path, content_type = blob
        data, _stored_type = await self._storage.download(path)
        return data, content_type
