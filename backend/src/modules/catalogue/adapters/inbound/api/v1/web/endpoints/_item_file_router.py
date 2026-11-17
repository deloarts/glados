"""
Shared route-building for the bought/made/source
item-file endpoints: list/download/upload/update/delete under
/{item_id}/files, plus the separate bulk list. Each of the 6 concrete
endpoint modules (bought_item_files.py, bought_items_files_bulk.py, ...)
shrinks to one `ItemFileEndpointConfig`/`ItemFileBulkEndpointConfig`
literal and a call here: route paths, status codes, dependency wiring
and response models are all read straight off the config, so
router.py's include_router() prefix/tags registrations (untouched) still
mount the exact same paths as before.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from types import GenericAlias
from typing import Annotated
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from fastapi import Depends
from fastapi import Form
from fastapi import Query
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User


class _RenameRequest(Protocol):
    @property
    def file_name(self) -> str: ...


ResponseT = TypeVar("ResponseT", bound=BaseModel)
UpdateRequestT = TypeVar("UpdateRequestT", bound=_RenameRequest)
CategoryT = TypeVar("CategoryT", bound=Enum)


@dataclass(frozen=True)
class ItemFileEndpointConfig(Generic[ResponseT, UpdateRequestT, CategoryT]):
    """One family's wire shape: every field is data (a schema class, a
    command class, a category enum, or a `deps/items.py` DI factory
    function), never a callable that varies request-handling logic per
    kind."""

    response_model: type[ResponseT]
    update_request_model: type[UpdateRequestT]
    update_command: type[BaseModel]
    category_enum: type[CategoryT]
    list_dep: Callable[..., Any]
    download_dep: Callable[..., Any]
    upload_dep: Callable[..., Any]
    update_dep: Callable[..., Any]
    delete_dep: Callable[..., Any]


def build_item_file_router(
    cfg: ItemFileEndpointConfig[ResponseT, UpdateRequestT, CategoryT],
) -> APIRouter:
    router = APIRouter()

    @router.get("/{item_id}/files", response_model=GenericAlias(list, (cfg.response_model,)))
    async def list_files(
        item_id: int,
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(cfg.list_dep),
    ) -> Any:
        return await use_case.execute(item_id=item_id)

    @router.get("/{item_id}/files/{file_id}")
    async def download_file(
        item_id: int,
        file_id: int,
        disposition: str = "attachment",
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(cfg.download_dep),
    ) -> Response:
        """Stream the file's raw bytes. Gated identically to the list route
        above (login only), never the write gate (a file download that
        requires write access is unusual)."""
        file, data, content_type = await use_case.execute(item_id=item_id, file_id=file_id)
        return file_download_response(
            data, file.file_name, content_type=content_type, disposition=disposition
        )

    async def upload_file(
        item_id: int,
        file: UploadFile,
        category: CategoryT = Form(...),
        actor: User = Depends(get_current_active_user),
        use_case: Any = Depends(cfg.upload_dep),
    ) -> Any:
        data, file_name, content_type = await read_upload(file)
        return await use_case.execute(
            actor=actor,
            item_id=item_id,
            data=data,
            file_name=file_name,
            content_type=content_type,
            category=category,
        )

    async def update_file(
        item_id: int,
        file_id: int,
        body: UpdateRequestT,
        actor: User = Depends(get_current_active_user),
        use_case: Any = Depends(cfg.update_dep),
    ) -> Any:
        return await use_case.execute(
            actor=actor,
            file_id=file_id,
            command=cfg.update_command(file_name=body.file_name),
        )

    async def delete_file(
        item_id: int,
        file_id: int,
        actor: User = Depends(get_current_active_user),
        use_case: Any = Depends(cfg.delete_dep),
    ) -> None:
        await use_case.execute(actor=actor, file_id=file_id)

    # FastAPI reads a parameter's class from its annotation, and the factory's
    # TypeVars name none, so the family's own classes go in before the routes
    # are registered.
    upload_file.__annotations__["category"] = cfg.category_enum
    update_file.__annotations__["body"] = cfg.update_request_model
    router.post(
        "/{item_id}/files",
        response_model=cfg.response_model,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(enforce_max_upload_size)],
    )(upload_file)
    router.patch("/{item_id}/files/{file_id}", response_model=cfg.response_model)(update_file)
    router.delete("/{item_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)(delete_file)

    return router


@dataclass(frozen=True)
class ItemFileBulkEndpointConfig(Generic[ResponseT]):
    response_model: type[ResponseT]
    list_dep: Callable[..., Any]


def build_bulk_item_file_router(cfg: ItemFileBulkEndpointConfig[ResponseT]) -> APIRouter:
    router = APIRouter()

    # Deliberately unpaginated: bounded per-item file attachments, and
    # item_ids itself is already capped (max_length=200 below).
    @router.get("/", response_model=GenericAlias(list, (cfg.response_model,)))
    async def list_files_for_items(
        item_ids: Annotated[list[int], Query(min_length=1, max_length=200)],
        _: User = Depends(get_current_active_user),
        use_case: Any = Depends(cfg.list_dep),
    ) -> Any:
        return await use_case.execute_many(item_ids=item_ids)

    return router
