"""
Shared route building for the pictures of made, bought and source items.
Each kind's endpoint module is one call here with its PictureDeps, so the
three surfaces stay identical:

  GET    /{item_id}/pictures                    every picture, the one shown marked
  GET    /{item_id}/picture/{variant}           the picture shown (image or thumbnail)
  GET    /{item_id}/pictures/{source}/{variant} one source's picture
  POST   /{item_id}/pictures                    upload the photo (the PICTURE source)
  DELETE /{item_id}/pictures/picture            delete the photo

and, under the kind's bulk prefix, `GET /?item_ids=` lists which picture is
shown for many items at once. Reading needs a login; uploading and deleting
need the permission to edit the item, checked by the use cases.
"""

from typing import Annotated
from typing import Any

from fastapi import Depends
from fastapi import Query
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.item_pictures import PictureDeps
from src.modules.catalogue.adapters.inbound.api.schemas.item_picture_schema import (
    ItemPictureInUseResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.item_picture_schema import (
    ItemPictureResponse,
)
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User


def build_item_picture_router(deps: PictureDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/{item_id}/pictures", response_model=list[ItemPictureResponse])
    async def list_pictures(
        item_id: int,
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(deps.list_dep),
    ) -> Any:
        return await use_case.execute(item_id)

    @router.get("/{item_id}/picture/{variant}")
    async def read_shown_picture(
        item_id: int,
        variant: ItemPictureVariant,
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(deps.download_dep),
    ) -> Response:
        """Stream the picture shown for the item, 404 without any."""
        data, content_type = await use_case.execute(item_id, variant)
        return file_download_response(
            data, f"{variant.value}.png", content_type=content_type, disposition="inline"
        )

    @router.get("/{item_id}/pictures/{source}/{variant}")
    async def read_picture(
        item_id: int,
        source: ItemPictureSource,
        variant: ItemPictureVariant,
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(deps.download_dep),
    ) -> Response:
        """Stream one source's picture, 404 when the item has none of it."""
        data, content_type = await use_case.execute(item_id, variant, source)
        return file_download_response(
            data,
            f"{source.value}-{variant.value}.png",
            content_type=content_type,
            disposition="inline",
        )

    @router.post(
        "/{item_id}/pictures",
        response_model=ItemPictureResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(enforce_max_upload_size)],
    )
    async def upload_picture(
        item_id: int,
        file: UploadFile,
        actor: User = Depends(get_current_active_user),
        use_case: Any = Depends(deps.upload_dep),
    ) -> Any:
        data, file_name, content_type = await read_upload(file)
        return await use_case.execute(actor, item_id, data, file_name, content_type)

    @router.delete("/{item_id}/pictures/picture", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_picture(
        item_id: int,
        actor: User = Depends(get_current_active_user),
        use_case: Any = Depends(deps.delete_dep),
    ) -> None:
        await use_case.execute(actor, item_id)

    return router


def build_bulk_item_picture_router(deps: PictureDeps) -> APIRouter:
    router = APIRouter()

    # Capped like the bulk file listing, one table page of item ids.
    @router.get("/", response_model=list[ItemPictureInUseResponse])
    async def list_pictures_in_use(
        item_ids: Annotated[list[int], Query(min_length=1, max_length=200)],
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(deps.list_dep),
    ) -> Any:
        return await use_case.execute_in_use(item_ids)

    return router
