"""
Serves the thumbnail a feed row links to. The signed token in the link is
the only credential: it names the item kind, id and variant and expires
within 90 minutes. An expired or forged token, an archived item or an item
without a picture all answer the same not-found, so the endpoint reveals
nothing beyond what a valid link already shows.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Protocol

from src.modules.catalogue.domain.policies.item_picture_selection import pick_picture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.operations.domain.errors import InfoscreenThumbnailNotFoundError
from src.modules.operations.infrastructure.security.terminal_auth import read_thumbnail_token
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class _Archivable(Protocol):
    archived: bool


class _ItemRepo(Protocol):
    async def get_by_id(self, id: int) -> _Archivable | None: ...


@dataclass(frozen=True)
class ServedThumbnail:
    data: bytes
    content_type: str
    max_age_seconds: int


class ServeInfoscreenThumbnail:
    def __init__(
        self,
        picture_repo: IItemPictureQueries,
        item_repos: dict[ItemKind, _ItemRepo],
        storage: IStoragePort | None,
        uow: IUnitOfWork,
    ) -> None:
        self._pictures = picture_repo
        self._items = item_repos
        self._storage = storage
        self._uow = uow

    async def execute(self, token: str) -> ServedThumbnail:
        now = now_utc()
        claims = read_thumbnail_token(token, now)
        if claims is None or self._storage is None:
            raise InfoscreenThumbnailNotFoundError("This thumbnail link is not valid.")
        raw_kind, item_id, raw_variant, expires = claims
        try:
            kind, variant = ItemKind(raw_kind), ItemPictureVariant(raw_variant)
        except ValueError as e:
            raise InfoscreenThumbnailNotFoundError("This thumbnail link is not valid.") from e

        item = await self._items[kind].get_by_id(item_id)
        if item is None or item.archived:
            raise InfoscreenThumbnailNotFoundError("This thumbnail link is not valid.")
        picture = pick_picture(await self._pictures.get_by_item(kind, item_id))
        blob = picture.blob(variant) if picture is not None else None
        if blob is None:
            raise InfoscreenThumbnailNotFoundError("This thumbnail link is not valid.")

        # Nothing was written; the connection goes back to the pool before
        # the storage download.
        await self._uow.commit()
        path, content_type = blob
        data, _stored_type = await self._storage.download(path)
        remaining = datetime.fromtimestamp(expires, UTC) - now
        return ServedThumbnail(
            data=data,
            content_type=content_type,
            max_age_seconds=max(0, int(remaining.total_seconds())),
        )
