"""
Serves the drawing a machine detail widget links to, which the display
embeds as a PDF. The signed token in the link is the only credential: it
names the made item and its drawing file and expires within 90 minutes. An
expired or forged token, an archived item or a drawing replaced since the
link was made all answer the same not-found.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemFileQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.operations.domain.errors import InfoscreenDrawingNotFoundError
from src.modules.operations.infrastructure.security.terminal_auth import read_drawing_token
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class ServedDrawing:
    data: bytes
    content_type: str
    file_name: str
    max_age_seconds: int


class ServeInfoscreenDrawing:
    def __init__(
        self,
        made_item_repo: IMadeItemQueries,
        file_repo: IMadeItemFileQueries,
        storage: IStoragePort | None,
        uow: IUnitOfWork,
    ) -> None:
        self._items = made_item_repo
        self._files = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(self, token: str) -> ServedDrawing:
        now = now_utc()
        claims = read_drawing_token(token, now)
        if claims is None or self._storage is None:
            raise InfoscreenDrawingNotFoundError("This drawing link is not valid.")
        item_id, file_id, expires = claims
        item = await self._items.get_by_id(item_id)
        if item is None or item.archived:
            raise InfoscreenDrawingNotFoundError("This drawing link is not valid.")
        drawings = await self._files.get_by_item_id_and_category(
            item_id, MadeItemFileCategory.DRAWING
        )
        drawing = next((f for f in drawings if f.id == file_id), None)
        if drawing is None:
            raise InfoscreenDrawingNotFoundError("This drawing link is not valid.")

        # Nothing was written; the connection goes back to the pool before
        # the storage download.
        await self._uow.commit()
        data, _stored_type = await self._storage.download(drawing.storage_path)
        remaining = datetime.fromtimestamp(expires, UTC) - now
        return ServedDrawing(
            data=data,
            content_type=drawing.mime_type or "application/pdf",
            file_name=drawing.file_name,
            max_age_seconds=max(0, int(remaining.total_seconds())),
        )
