"""
Brings a bought item's Data Portal picture (the DATA_PORTAL item picture)
in line with its portal link after a BoughtItemEdpPictureRequested event.
A linked item gets the portal part's product picture, whatever photo or
CAD rendering it already has, since each source keeps its own picture; an
item no longer linked loses its portal picture. The part is read again by
the item's own edp_part_id rather than taken from the event, so only a
link Glados stored is ever followed. A picture already fetched for the
same part is kept, so a repeated lookup costs no download.

Runs in the event worker, off the request, as the system user, through
ItemPictureStore, so the picture gets the same processing as an upload.
Nothing happens while storage or the portal is off, for an archived or
missing item, or for a part without a picture; a portal failure is logged
and the event is not retried, since the next lookup on the item requests
the picture again.
"""

from src.modules.catalogue.application.facade.item_commands import ItemPictureStore
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_SOURCE = ItemPictureSource.DATA_PORTAL


def edp_picture_file_name(edp_part_id: int) -> str:
    """The file name a portal picture is stored under, which also records
    the part it was fetched for."""
    return f"edp-{edp_part_id}.png"


class FillBoughtItemEdpPicture:
    def __init__(
        self,
        item_repo: IBoughtItemCadStore,
        picture_repo: IItemPictureQueries,
        settings_repo: IExternalDataSettingsRepository,
        user_repo: IUserRepository,
        portal_factory: IEplanDataPortalFactory,
        store: ItemPictureStore | None,
        uow: IUnitOfWork,
    ) -> None:
        self._items = item_repo
        self._pictures = picture_repo
        self._settings = settings_repo
        self._users = user_repo
        self._portal_factory = portal_factory
        # None while storage is off; the worker builds the store only with
        # a storage adapter.
        self._store = store
        self._uow = uow

    async def execute(self, event: BoughtItemEdpPictureRequested) -> None:
        if self._store is None:
            return
        item = await self._items.get_by_id(event.item_id)
        if item is None or item.archived:
            return
        if item.edp_part_id is None:
            await self._remove(item.id)
            return
        current = await self._pictures.get_by_source(ItemKind.BOUGHT, item.id, _SOURCE)
        file_name = edp_picture_file_name(item.edp_part_id)
        if current is not None and current.file_name == file_name:
            return
        settings = await self._settings.get_edp()
        if not settings.enabled or not settings.pat:
            return
        actor = await self._system_actor()
        portal = self._portal_factory(EdpConnection(base_url=settings.base_url, pat=settings.pat))

        # Nothing has been written. Ending the read transaction hands the
        # connection back to the pool for the portal calls.
        await self._uow.commit()
        try:
            parts = await portal.get_parts([item.edp_part_id])
            url = parts[0].picture_url if parts else None
            picture = await portal.fetch_picture(url) if url else None
        except DomainError as exc:
            log.warning(f"Data Portal picture for bought item #{item.id} not loaded: {exc}")
            return
        if picture is None:
            return

        try:
            staged = await self._store.stage(
                ItemKind.BOUGHT, item.id, _SOURCE, picture, file_name, actor.id
            )
        except DomainError as exc:
            log.warning(f"Data Portal picture for bought item #{item.id} not stored: {exc}")
            return
        try:
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            await self._store.discard(staged)
            raise
        await self._store.finish(staged)
        log.info(f"Stored the Data Portal picture of bought item #{item.id}.")

    async def _remove(self, item_id: int) -> None:
        assert self._store is not None  # checked by execute
        paths = await self._store.stage_removal(ItemKind.BOUGHT, item_id, _SOURCE)
        if paths is None:
            return
        await self._uow.commit()
        await self._store.remove_blobs(paths, context=f"unlinked bought item #{item_id}")
        log.info(f"Removed the Data Portal picture of unlinked bought item #{item_id}.")

    async def _system_actor(self) -> User:
        actor = await self._users.get_by_username(SYSTEM_USER)
        if actor is None:
            raise RuntimeError("System user not found; init_db must seed it first.")
        return actor
