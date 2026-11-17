"""Dependency factories for the picture use cases of made, bought and source
items. The three kinds differ only in their PictureKind, their item
repository and, for made items, the newest-revision rule, so one builder
makes each kind's set of factories.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_item_picture_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.application.use_cases.item_picture._kinds import BOUGHT_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture._kinds import MADE_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture._kinds import SOURCE_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureKind
from src.modules.catalogue.application.use_cases.item_picture.delete_item_picture import (
    DeleteItemPicture,
)
from src.modules.catalogue.application.use_cases.item_picture.download_item_picture import (
    DownloadItemPicture,
)
from src.modules.catalogue.application.use_cases.item_picture.list_item_pictures import (
    ListItemPictures,
)
from src.modules.catalogue.application.use_cases.item_picture.upload_item_picture import (
    EditableCheck,
)
from src.modules.catalogue.application.use_cases.item_picture.upload_item_picture import (
    UploadItemPicture,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


@dataclass(frozen=True)
class PictureDeps:
    list_dep: Callable[..., ListItemPictures]
    download_dep: Callable[..., DownloadItemPicture]
    upload_dep: Callable[..., UploadItemPicture]
    delete_dep: Callable[..., DeleteItemPicture]


def _no_editable_check() -> EditableCheck | None:
    return None


def _made_item_editable_check(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> EditableCheck | None:
    """A made item's photo follows its files: only the newest revision may
    change while the admin setting asks for that."""

    async def check(item: MadeItem) -> None:
        await assert_made_item_editable(item, made_item_repo, admin_settings_repo)

    return check


def _build(
    kind: PictureKind,
    item_repo_dep: Callable[..., Any],
    editable_check_dep: Callable[..., EditableCheck | None] = _no_editable_check,
) -> PictureDeps:
    def list_dep(
        item_repo: Any = Depends(item_repo_dep),
        picture_repo: IItemPictureRepository = Depends(get_item_picture_repo),
    ) -> ListItemPictures:
        return ListItemPictures(kind, item_repo, picture_repo)

    def download_dep(
        picture_repo: IItemPictureRepository = Depends(get_item_picture_repo),
        storage: IStoragePort | None = Depends(get_optional_storage_adapter),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> DownloadItemPicture:
        return DownloadItemPicture(kind, picture_repo, storage, uow)

    def upload_dep(
        item_repo: Any = Depends(item_repo_dep),
        picture_repo: IItemPictureRepository = Depends(get_item_picture_repo),
        storage: IStoragePort | None = Depends(get_optional_storage_adapter),
        uow: IUnitOfWork = Depends(get_unit_of_work),
        editable_check: EditableCheck | None = Depends(editable_check_dep),
    ) -> UploadItemPicture:
        return UploadItemPicture(
            kind, item_repo, picture_repo, storage, uow=uow, editable_check=editable_check
        )

    def delete_dep(
        item_repo: Any = Depends(item_repo_dep),
        picture_repo: IItemPictureRepository = Depends(get_item_picture_repo),
        storage: IStoragePort | None = Depends(get_optional_storage_adapter),
        uow: IUnitOfWork = Depends(get_unit_of_work),
        editable_check: EditableCheck | None = Depends(editable_check_dep),
    ) -> DeleteItemPicture:
        return DeleteItemPicture(
            kind, item_repo, picture_repo, storage, uow=uow, editable_check=editable_check
        )

    return PictureDeps(
        list_dep=list_dep, download_dep=download_dep, upload_dep=upload_dep, delete_dep=delete_dep
    )


MADE_ITEM_PICTURE_DEPS = _build(MADE_ITEM_PICTURES, get_made_item_repo, _made_item_editable_check)
BOUGHT_ITEM_PICTURE_DEPS = _build(BOUGHT_ITEM_PICTURES, get_bought_item_repo)
SOURCE_ITEM_PICTURE_DEPS = _build(SOURCE_ITEM_PICTURES, get_source_item_repo)
