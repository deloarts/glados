"""
Stores and removes item pictures for every writer: a person's upload, the
EPLAN Data Portal worker and PDM. A picture is decoded and cleaned up like
any uploaded product image (process_image_for_upload), and its thumbnail
is always derived from it, never supplied separately.

Writing follows the same order as the item file uploads: the new blobs are
stored before any row changes, the new row is written together with the
removal of the picture it replaces (one per source), and the replaced
blobs are removed only once the caller has committed. So a failure at any
step never loses the picture already there. `stage` writes without
committing; the caller commits and then passes the result to `finish`, or
rolls back and passes it to `discard`.
"""

import hashlib
import uuid
from dataclasses import dataclass
from dataclasses import field

from anyio import to_thread

from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.errors import ItemPictureInvalidTypeError
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.platform.application.services.image_processing import IMAGE_DECODE_ERRORS
from src.modules.platform.application.services.image_processing import MAX_IMAGE_PIXELS
from src.modules.platform.application.services.image_processing import process_image_for_upload
from src.modules.platform.application.services.image_processing import shrink_image
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.shared_kernel.domain.services.clock import now_utc

# Longest side of a thumbnail, small enough for a table cell at any screen
# density and far below what a full image costs to download.
THUMBNAIL_MAX_SIDE = 512

_PNG = "image/png"

_STORAGE_PREFIXES: dict[ItemKind, str] = {
    ItemKind.MADE: "made_items/pictures",
    ItemKind.BOUGHT: "bought_items/pictures",
    ItemKind.SOURCE: "source_items/pictures",
}


@dataclass(frozen=True)
class StagedItemPicture:
    """A picture whose blobs are stored and whose row changes are written
    but not committed. `new_paths` are its own blobs, removed by `discard`;
    `replaced_paths` those of the picture it replaces, removed by `finish`."""

    picture: ItemPicture
    new_paths: list[str]
    replaced_paths: list[str] = field(default_factory=list)


def _process(data: bytes, thumbnail_only: bool) -> tuple[bytes | None, bytes, str]:
    """(image, thumbnail, sha256 of the larger of the two kept)."""
    image = process_image_for_upload(data)
    thumbnail = shrink_image(image, THUMBNAIL_MAX_SIDE)
    kept = None if thumbnail_only else image
    return kept, thumbnail, hashlib.sha256(kept if kept is not None else thumbnail).hexdigest()


class ItemPictureStore:
    def __init__(self, picture_repo: IItemPictureRepository, storage: IStoragePort) -> None:
        self._pictures = picture_repo
        self._storage = storage

    async def stage(
        self,
        kind: ItemKind,
        item_id: int,
        source: ItemPictureSource,
        data: bytes,
        file_name: str,
        uploaded_by_user_id: int,
        *,
        thumbnail_only: bool = False,
    ) -> StagedItemPicture:
        """Processes `data`, stores the image and its thumbnail (only the
        thumbnail with `thumbnail_only`, for an image that is no more than
        one, such as PDM's check-in rendering) and writes the row that
        replaces `source`'s current picture. Raises
        ItemPictureInvalidTypeError for data that is not an image."""
        try:
            image, thumbnail, digest = await to_thread.run_sync(_process, data, thumbnail_only)
        except IMAGE_DECODE_ERRORS as exc:
            raise ItemPictureInvalidTypeError(
                f"{file_name!r} could not be decoded as an image, or has more than"
                f" {MAX_IMAGE_PIXELS:,} pixels."
            ) from exc

        base = f"{_STORAGE_PREFIXES[kind]}/{item_id}/{source.value}/{uuid.uuid4()}"
        image_path = f"{base}.png" if image is not None else None
        thumbnail_path = f"{base}-thumbnail.png"
        new_paths: list[str] = []
        try:
            if image is not None and image_path is not None:
                await self._storage.upload(image_path, image, _PNG)
                new_paths.append(image_path)
            await self._storage.upload(thumbnail_path, thumbnail, _PNG)
            new_paths.append(thumbnail_path)

            existing = await self._pictures.get_by_source(kind, item_id, source)
            if existing is not None:
                # The unique (item, source) constraint needs the old row gone
                # before the new one is inserted.
                await self._pictures.delete(existing)
            saved = await self._pictures.save(
                ItemPicture(
                    id=0,
                    item_kind=kind,
                    item_id=item_id,
                    source=source,
                    file_name=file_name,
                    image_path=image_path,
                    image_mime_type=_PNG if image is not None else None,
                    image_size_bytes=len(image) if image is not None else None,
                    thumbnail_path=thumbnail_path,
                    thumbnail_mime_type=_PNG,
                    thumbnail_size_bytes=len(thumbnail),
                    sha256=digest,
                    created=now_utc(),
                    uploaded_by_user_id=uploaded_by_user_id,
                )
            )
        except Exception:
            await self.remove_blobs(new_paths, context="discarding an unsaved item picture")
            raise
        return StagedItemPicture(
            picture=saved,
            new_paths=new_paths,
            replaced_paths=existing.storage_paths() if existing is not None else [],
        )

    async def stage_removal(
        self, kind: ItemKind, item_id: int, source: ItemPictureSource
    ) -> list[str] | None:
        """Deletes `source`'s picture row without committing and returns the
        blobs to remove once the caller has committed; None when the item
        has no picture of that source."""
        existing = await self._pictures.get_by_source(kind, item_id, source)
        if existing is None:
            return None
        await self._pictures.delete(existing)
        return existing.storage_paths()

    async def finish(self, staged: StagedItemPicture) -> None:
        await self.remove_blobs(staged.replaced_paths, context="replacing an item picture")

    async def discard(self, staged: StagedItemPicture) -> None:
        await self.remove_blobs(staged.new_paths, context="discarding an uncommitted item picture")

    async def remove_blobs(self, paths: list[str], *, context: str) -> None:
        for path in paths:
            await delete_storage_object_best_effort(self._storage, path, context=context)
