"""Generic use-case core behind the file attachment operations of bought, made
and source items, products, orders and production orders. Each concrete
class (e.g. UploadBoughtItemFile in upload_bought_item_file.py) is a small
subclass supplying its `_kind`, an `ItemFileKind`; families whose
constructor or `execute` keywords name the parent (`product_id`,
`order_id`) override those signatures only to keep the callers' keywords.
Families whose rules do not fit a shared step (the product's write rule,
the order's validation messages) override one hook rather than adding
branches here.

Upload and download end the request's read transaction before the slow
storage step, so no pooled connection sits idle while bytes move. Upload
also stores the new blob before any row changes, commits the new row
together with the removal of any row it replaces, and removes a replaced
blob only after that commit, so a failure at any step never loses the
existing file. Delete removes the row and commits before it removes the
blob, for the same reason."""

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from anyio import to_thread

from src.modules.platform.application.services.file_attachments.config import ItemFileEntity
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.image_processing import IMAGE_DECODE_ERRORS
from src.modules.platform.application.services.image_processing import MAX_IMAGE_PIXELS
from src.modules.platform.application.services.image_processing import process_image_for_upload
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.application.services.svg_optimizer import optimize_svg
from src.modules.platform.application.services.svg_sanitizer import SvgRejectedError
from src.modules.platform.application.services.svg_sanitizer import sanitize_svg
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.services.content_types import content_type_for
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

TFile = TypeVar("TFile", bound=ItemFileEntity)
TResult = TypeVar("TResult")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ILinkedFiles(Protocol):
    """Which of the given files an outside source, such as the CAD vault,
    manages, so the file lists can mark them."""

    async def get_linked_item_file_ids(self, item_file_ids: list[int]) -> set[int]: ...


class _ItemRepo(Protocol):
    """Structural shape shared by the parent repositories: only `get_by_id`
    is called here, to check the parent exists before touching its files."""

    async def get_by_id(self, id: int) -> object | None: ...


class _FileRepo(Protocol[TFile]):
    """The file repository methods the bases call. `category` is `Any`
    because the families' category enums share no supertype."""

    async def get_by_id(self, id: int) -> TFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[TFile]: ...
    async def get_by_item_id_and_category(self, item_id: int, category: Any) -> list[TFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[TFile]: ...
    async def save(self, file: TFile) -> TFile: ...
    async def delete(self, file: TFile) -> None: ...


@dataclass(frozen=True)
class StagedItemFile(Generic[TFile]):
    """A file whose blob is stored and whose row changes are written but not
    committed. `replaced_storage_paths` are the blobs of the singleton rows
    it replaces, removed only once the caller's commit has succeeded."""

    file: TFile
    replaced_storage_paths: list[str]


class GetItemFilesBase(Generic[TFile, TResult]):
    _kind: ItemFileKind[TFile, TResult, Any]

    def __init__(
        self,
        item_repo: _ItemRepo,
        file_repo: _FileRepo[TFile],
        storage: IStoragePort | None,
        pdm_document_link_repo: ILinkedFiles | None = None,
    ) -> None:
        self._item_repo = item_repo
        self._file_repo = file_repo
        self._storage = storage
        # Absent for source items, which have no PDM documents.
        self._pdm_links = pdm_document_link_repo

    async def _from_pdm_ids(self, file_ids: list[int]) -> set[int]:
        """One query for a whole listing's `from_pdm` flag: see
        ItemFileKind.to_result's docstring."""
        if self._pdm_links is None or not file_ids:
            return set()
        return await self._pdm_links.get_linked_item_file_ids(file_ids)

    async def execute(self, item_id: int) -> list[TResult]:
        cfg = self._kind
        if not await self._item_repo.get_by_id(item_id):
            raise cfg.item_not_found_error(f"{cfg.item_label.capitalize()} #{item_id} not found.")
        files = await self._file_repo.get_by_item_id(item_id)
        from_pdm_ids = await self._from_pdm_ids([f.id for f in files])
        return [cfg.to_result(f, self._storage, from_pdm=f.id in from_pdm_ids) for f in files]

    async def execute_many(self, item_ids: list[int]) -> list[TResult]:
        """Files for several items in one pass, as a flat list the caller
        groups. An unknown item id is not an error, since a list may race a
        deletion."""
        cfg = self._kind
        files = await self._file_repo.get_by_item_ids(item_ids)
        from_pdm_ids = await self._from_pdm_ids([f.id for f in files])
        return [cfg.to_result(f, self._storage, from_pdm=f.id in from_pdm_ids) for f in files]


class UploadItemFileBase(Generic[TFile, TResult]):
    _kind: ItemFileKind[TFile, TResult, Any]

    def __init__(
        self,
        item_repo: _ItemRepo,
        file_repo: _FileRepo[TFile],
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._item_repo = item_repo
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def _assert_editable(self, item: Any) -> None:
        """Extension point for a kind-specific rule beyond assert_can_update
        (made items have a newest-only rule, see UploadMadeItemFile).
        No-op for the other families, which have no such rule."""
        return

    async def _load_writable_item(self, actor: User, item_id: int) -> Any:
        """Checks the write permission, that storage is enabled and that the
        parent exists, in that order, and returns the parent. Products
        override this because their write rule needs the loaded product."""
        cfg = self._kind
        # Attachments need the same permission as editing the parent.
        cfg.assert_can_update(actor)

        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")

        item = await self._item_repo.get_by_id(item_id)
        if not item:
            raise cfg.item_not_found_error(f"{cfg.item_label.capitalize()} #{item_id} not found.")
        await self._assert_editable(item)
        return item

    def _validate_upload(self, category: Any, content_type: str, file_name: str, size: int) -> str:
        """Returns the stored extension or raises. Orders and production
        orders override it with their own error messages."""
        return self._kind.validate_upload(category, content_type, file_name, size)

    async def _store_blob(
        self,
        actor: User,
        item_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: Any,
    ) -> TFile:
        """Checks permission, parent and upload, processes the bytes and
        stores the blob, and returns the unsaved row describing it."""
        cfg = self._kind
        await self._load_writable_item(actor, item_id)
        assert self._storage is not None  # _load_writable_item refuses to run without storage

        ext = self._validate_upload(category, content_type, file_name, len(data))

        # Nothing has been written yet. Ending the read transaction hands the
        # connection back to the pool for the image processing, hashing and
        # storage upload, which take far longer than any query here.
        await self._uow.commit()

        if ext == ".svg":
            try:
                data = await to_thread.run_sync(sanitize_svg, data)
            except SvgRejectedError as exc:
                raise cfg.file_invalid_type_error(
                    f"Uploaded {category.value} is not an SVG drawing that can be kept: {exc}"
                ) from exc
            data = await to_thread.run_sync(optimize_svg, data)
        elif category in cfg.image_categories:
            try:
                data = await to_thread.run_sync(process_image_for_upload, data)
            except IMAGE_DECODE_ERRORS as exc:
                raise cfg.file_invalid_type_error(
                    f"Uploaded {category.value} could not be decoded as an image, or has more"
                    f" than {MAX_IMAGE_PIXELS:,} pixels."
                ) from exc
            ext = ".png"

        # The stored type follows the stored extension, never the type the
        # client sent, so a file cannot reach a browser as HTML.
        content_type = content_type_for(ext)

        stored_name = f"{uuid.uuid4()}{ext}"
        storage_path = f"{cfg.storage_prefix}/{item_id}/{category.value}/{stored_name}"
        sha256 = await to_thread.run_sync(_sha256_hex, data)

        await self._storage.upload(storage_path, data, content_type)

        return cfg.make_entity(
            item_id=item_id,
            file_name=file_name,
            stored_name=stored_name,
            mime_type=content_type,
            size_bytes=len(data),
            storage_path=storage_path,
            sha256=sha256,
            category=category,
            created=now_utc(),
            uploaded_by_user_id=actor.id,
        )

    async def execute(
        self,
        actor: User,
        item_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: Any,
    ) -> TResult:
        cfg = self._kind
        record = await self._store_blob(actor, item_id, data, file_name, content_type, category)
        assert self._storage is not None  # _store_blob refuses to run without storage
        storage_path = record.storage_path
        try:
            existing = (
                await self._file_repo.get_by_item_id_and_category(item_id, category)
                if category.is_singleton()
                else []
            )
            saved = await self._file_repo.save(record)
            # A singleton category holds one file, so the rows it replaces go
            # in the same commit as the new row.
            for old in existing:
                await self._file_repo.delete(old)
            await self._uow.commit()
        except Exception:
            await delete_storage_object_best_effort(
                self._storage,
                storage_path,
                context=f"discarding unsaved {category.value} file for {cfg.item_label} #{item_id}",
            )
            raise

        # The replaced blobs go only once that commit has succeeded, so a
        # failure before it leaves the old file intact.
        for old in existing:
            await delete_storage_object_best_effort(
                self._storage,
                old.storage_path,
                context=f"replacing {category.value} file for {cfg.item_label} #{item_id}",
            )

        url = get_storage_url_best_effort(
            self._storage,
            saved.storage_path,
            context=f"{cfg.item_label} file #{saved.id}",
            file_name=saved.file_name,
        )

        log.info(
            f"File uploaded for {cfg.item_label} #%s: %r (%s, %s bytes, category=%s) by user #%s.",
            item_id,
            file_name,
            saved.mime_type,
            saved.size_bytes,
            category.value,
            actor.id,
        )
        return cfg.to_result(saved, self._storage, url=url)

    async def stage(
        self,
        actor: User,
        item_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: Any,
    ) -> StagedItemFile[TFile]:
        """Same checks and blob handling as execute, but the new row and the
        removal of any singleton rows it replaces are written without a
        commit, so the caller commits them in one transaction with its own
        related writes. After that commit the caller passes the result to
        finish_staged; if anything fails first, it rolls back and passes it
        to discard_staged, so neither a row nor a blob is left behind."""
        cfg = self._kind
        record = await self._store_blob(actor, item_id, data, file_name, content_type, category)
        try:
            existing = (
                await self._file_repo.get_by_item_id_and_category(item_id, category)
                if category.is_singleton()
                else []
            )
            saved = await self._file_repo.save(record)
            for old in existing:
                await self._file_repo.delete(old)
        except Exception:
            await self.discard_staged(StagedItemFile(file=record, replaced_storage_paths=[]))
            raise
        log.info(
            f"File staged for {cfg.item_label} #%s: %r (%s, %s bytes, category=%s).",
            item_id,
            file_name,
            saved.mime_type,
            saved.size_bytes,
            category.value,
        )
        return StagedItemFile(
            file=saved, replaced_storage_paths=[old.storage_path for old in existing]
        )

    async def finish_staged(self, staged: StagedItemFile[Any]) -> None:
        """Removes the blobs of the rows a committed staged file replaced."""
        assert self._storage is not None  # a staged file implies storage
        for path in staged.replaced_storage_paths:
            await delete_storage_object_best_effort(
                self._storage, path, context=f"replacing {self._kind.item_label} file"
            )

    async def discard_staged(self, staged: StagedItemFile[Any]) -> None:
        """Removes the blob of a staged file whose rows were never committed."""
        assert self._storage is not None  # a staged file implies storage
        await delete_storage_object_best_effort(
            self._storage,
            staged.file.storage_path,
            context=f"discarding uncommitted {self._kind.item_label} file",
        )


class UpdateItemFileBase(Generic[TFile, TResult]):
    _kind: ItemFileKind[TFile, TResult, Any]

    def __init__(
        self, file_repo: _FileRepo[TFile], storage: IStoragePort | None, *, uow: IUnitOfWork
    ) -> None:
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def _assert_editable(self, file: Any) -> None:
        """Extension point for a kind-specific rule beyond assert_can_update
        (made items have a newest-only rule, see UpdateMadeItemFile).
        No-op for bought/source items, which have no such rule."""
        return

    async def execute(self, actor: User, file_id: int, command: Any) -> TResult:
        cfg = self._kind
        cfg.assert_can_update(actor)

        file = await self._file_repo.get_by_id(file_id)
        if not file:
            raise cfg.file_not_found_error(f"File #{file_id} not found.")
        await self._assert_editable(file)

        file.file_name = command.file_name
        saved = await self._file_repo.save(file)
        await self._uow.commit()
        log.info(
            f"{cfg.item_label.capitalize()} file #%s renamed to %r.", file_id, command.file_name
        )

        return cfg.to_result(saved, self._storage)


class DeleteItemFileBase(Generic[TFile]):
    _kind: ItemFileKind[TFile, Any, Any]

    def __init__(
        self, file_repo: _FileRepo[TFile], storage: IStoragePort | None, *, uow: IUnitOfWork
    ) -> None:
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def _assert_editable(self, file: Any) -> None:
        """Extension point for a kind-specific rule beyond assert_can_update
        (made items have a newest-only rule, see DeleteMadeItemFile).
        No-op for bought/source items, which have no such rule."""
        return

    async def execute(self, actor: User, file_id: int) -> None:
        cfg = self._kind
        cfg.assert_can_update(actor)

        file = await self._file_repo.get_by_id(file_id)
        if not file:
            raise cfg.file_not_found_error(f"File #{file_id} not found.")
        await self._assert_editable(file)

        await self._file_repo.delete(file)
        await self._uow.commit()

        # The blob goes only once the row deletion has committed, so a failed
        # commit leaves the row with its file intact. A failed blob delete
        # leaves an orphan, which is logged and not raised.
        if self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage,
                file.storage_path,
                context=f"deleting {cfg.item_label} file #{file_id}",
            )
        log.info(f"{cfg.item_label.capitalize()} file #%s (%r) deleted.", file_id, file.file_name)


class DownloadItemFileBase(Generic[TFile]):
    _kind: ItemFileKind[TFile, Any, Any]

    def __init__(
        self,
        file_repo: _FileRepo[TFile],
        storage: IStoragePort | None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(self, item_id: int, file_id: int) -> tuple[TFile, bytes, str]:
        cfg = self._kind
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")

        file = await self._file_repo.get_by_id(file_id)
        if not file or getattr(file, cfg.fk_field) != item_id:
            # A file id that exists but belongs to another parent 404s,
            # never 403s: there is no cross-parent existence oracle.
            raise cfg.file_not_found_error(f"File #{file_id} not found.")

        # Nothing has been written. Ending the read transaction hands the
        # connection back to the pool for the storage download.
        if self._uow is not None:
            await self._uow.commit()

        # The type follows the stored extension rather than what storage
        # recorded, see content_types.py.
        data, _ = await self._storage.download(file.storage_path)
        return file, data, content_type_for(file.storage_path)
