"""
Characterisation suite: pins the observable behaviour of the
bought/made/source item-file use cases (get/upload/update/delete/download),
which share the _item_files generic core, so the three kinds keep behaving
identically except where they genuinely differ.

Every test is parametrised over the three kinds via _SPECS (ids=bought/
made/source) unless it targets a specific, real divergence between them
(DXF/DRAWING on made only, STEP/MESH absent from
source, and a genuine wording difference in the PDF-content-type-
mismatch message; see TestPdfFallbackMessageWording below). Only
existing, already-public collaborator shapes are used (repository
Protocols, IStoragePort); nothing here reaches into the use cases'
internal structure.
"""

import io
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from src.modules.catalogue.application.dto.bought_item_file_dto import UpdateBoughtItemFileCommand
from src.modules.catalogue.application.dto.made_item_file_dto import UpdateMadeItemFileCommand
from src.modules.catalogue.application.dto.source_item_file_dto import UpdateSourceItemFileCommand
from src.modules.catalogue.application.use_cases.bought_item.delete_bought_item_file import (
    DeleteBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.download_bought_item_file import (
    DownloadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item_files import (
    GetBoughtItemFiles,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item_file import (
    UpdateBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.upload_bought_item_file import (
    UploadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.delete_made_item_file import (
    DeleteMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.download_made_item_file import (
    DownloadMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.get_made_item_files import (
    GetMadeItemFiles,
)
from src.modules.catalogue.application.use_cases.made_item.update_made_item_file import (
    UpdateMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.delete_source_item_file import (
    DeleteSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.download_source_item_file import (
    DownloadSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.get_source_item_files import (
    GetSourceItemFiles,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item_file import (
    UpdateSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.upload_source_item_file import (
    UploadSourceItemFile,
)
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.errors import BoughtItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import BoughtItemFileNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemFileTooLargeError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import MadeItemFileNotFoundError
from src.modules.catalogue.domain.errors import MadeItemFileTooLargeError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import SourceItemFileNotFoundError
from src.modules.catalogue.domain.errors import SourceItemFileTooLargeError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.fulfillment.application.use_cases.order.delete_order_file import DeleteOrderFile
from src.modules.fulfillment.application.use_cases.production_order.delete_production_order_file import (
    DeleteProductionOrderFile,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.workspace.application.use_cases.product.delete_product_file import (
    DeleteProductFile,
)
from tests.unit.fakes import FakeUnitOfWork

# ── Generic fakes (kind-agnostic: every repo/storage Protocol here is
# identical in shape across bought/made/source) ──────────────────────────


class _FakeItemRepo:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    async def get_by_id(self, id: int) -> object | None:
        return object() if self._exists else None


class _FakeFileRepo:
    def __init__(self, files: list[Any] | None = None) -> None:
        self.files: list[Any] = list(files or [])
        self.deleted: list[Any] = []
        self._next_id = max((f.id for f in self.files), default=0) + 1

    async def get_by_id(self, id: int) -> Any | None:
        return next((f for f in self.files if f.id == id), None)

    async def get_by_item_id(self, item_id: int) -> list[Any]:
        return list(self.files)

    async def get_by_item_ids(self, item_ids: list[int]) -> list[Any]:
        return list(self.files)

    async def get_by_item_id_and_category(self, item_id: int, category: Any) -> list[Any]:
        return [f for f in self.files if f.category == category]

    async def save(self, file: Any) -> Any:
        if file.id == 0:
            file.id = self._next_id
            self._next_id += 1
            self.files.append(file)
        else:
            for i, f in enumerate(self.files):
                if f.id == file.id:
                    self.files[i] = file
                    break
        return file

    async def delete(self, file: Any) -> None:
        self.deleted.append(file)
        self.files = [f for f in self.files if f.id != file.id]


class _RecordingStorage:
    """Records call order (not just presence): the singleton-replace and
    delete flows both remove a blob only after the commit that drops its
    row, and this is what proves it."""

    def __init__(self, objects: dict[str, tuple[bytes, str]] | None = None) -> None:
        self.objects: dict[str, tuple[bytes, str]] = dict(objects or {})
        self.calls: list[str] = []

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.calls.append(f"upload:{key}")
        self.objects[key] = (data, content_type)

    async def download(self, key: str) -> tuple[bytes, str]:
        self.calls.append(f"download:{key}")
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.calls.append(f"delete:{key}")
        self.objects.pop(key, None)

    def get_url(self, key: str, file_name: str | None = None) -> str:
        self.calls.append(f"get_url:{key}")
        return f"https://storage.test/{key}"


class _FailingDeleteStorage(_RecordingStorage):
    """Storage whose delete raises, standing in for a backend that drops out
    after the row deletion has committed."""

    async def delete(self, key: str) -> None:
        raise RuntimeError("storage unavailable")


class _SequencedFileRepo(_FakeFileRepo):
    """Writes its saves and deletes into a log shared with the storage and
    unit of work fakes, so a test can assert the order across all three."""

    def __init__(
        self, log: list[str], files: list[Any] | None = None, fail_save: bool = False
    ) -> None:
        super().__init__(files)
        self._log = log
        self._fail_save = fail_save

    async def save(self, file: Any) -> Any:
        if self._fail_save:
            self._log.append("save:failed")
            raise RuntimeError("database unavailable")
        saved = await super().save(file)
        self._log.append(f"save:{saved.id}")
        return saved

    async def delete(self, file: Any) -> None:
        self._log.append(f"delete_row:{file.id}")
        await super().delete(file)


class _RecordingUow:
    """Logs its commits; with `fail_commit_number` set, that commit (counted
    from 1) raises instead, standing in for a database that drops out."""

    def __init__(self, log: list[str], fail_commit_number: int | None = None) -> None:
        self._log = log
        self._fail_commit_number = fail_commit_number
        self._commits = 0

    async def commit(self) -> None:
        self._commits += 1
        if self._commits == self._fail_commit_number:
            self._log.append("commit:failed")
            raise RuntimeError("database unavailable")
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


def _writer(permission: str) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=[permission],
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (10, 20, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


# ── Per-kind spec table ─────────────────────────────────────────────────


@dataclass(frozen=True)
class _KindSpec:
    id: str
    item_label: str  # capitalized, e.g. "Bought item"
    get_uc: type
    upload_uc: type
    update_uc: type
    delete_uc: type
    download_uc: type
    file_entity: type
    category: type
    item_not_found: type[Exception]
    file_not_found: type[Exception]
    too_large: type[Exception]
    invalid_type: type[Exception]
    update_command: type
    fk_field: str
    write_permission: str
    storage_prefix: str


_BOUGHT = _KindSpec(
    id="bought",
    item_label="Bought item",
    get_uc=GetBoughtItemFiles,
    upload_uc=UploadBoughtItemFile,
    update_uc=UpdateBoughtItemFile,
    delete_uc=DeleteBoughtItemFile,
    download_uc=DownloadBoughtItemFile,
    file_entity=BoughtItemFile,
    category=BoughtItemFileCategory,
    item_not_found=BoughtItemNotFoundError,
    file_not_found=BoughtItemFileNotFoundError,
    too_large=BoughtItemFileTooLargeError,
    invalid_type=BoughtItemFileInvalidTypeError,
    update_command=UpdateBoughtItemFileCommand,
    fk_field="bought_item_id",
    write_permission=Permission.WRITE_BOUGHT_ITEMS,
    storage_prefix="bought_items/catalogue",
)
_MADE = _KindSpec(
    id="made",
    item_label="Made item",
    get_uc=GetMadeItemFiles,
    upload_uc=UploadMadeItemFile,
    update_uc=UpdateMadeItemFile,
    delete_uc=DeleteMadeItemFile,
    download_uc=DownloadMadeItemFile,
    file_entity=MadeItemFile,
    category=MadeItemFileCategory,
    item_not_found=MadeItemNotFoundError,
    file_not_found=MadeItemFileNotFoundError,
    too_large=MadeItemFileTooLargeError,
    invalid_type=MadeItemFileInvalidTypeError,
    update_command=UpdateMadeItemFileCommand,
    fk_field="made_item_id",
    write_permission=Permission.WRITE_MADE_ITEMS,
    storage_prefix="made_items/catalogue",
)
_SOURCE = _KindSpec(
    id="source",
    item_label="Source item",
    get_uc=GetSourceItemFiles,
    upload_uc=UploadSourceItemFile,
    update_uc=UpdateSourceItemFile,
    delete_uc=DeleteSourceItemFile,
    download_uc=DownloadSourceItemFile,
    file_entity=SourceItemFile,
    category=SourceItemFileCategory,
    item_not_found=SourceItemNotFoundError,
    file_not_found=SourceItemFileNotFoundError,
    too_large=SourceItemFileTooLargeError,
    invalid_type=SourceItemFileInvalidTypeError,
    update_command=UpdateSourceItemFileCommand,
    fk_field="source_item_id",
    write_permission=Permission.WRITE_SOURCE_ITEMS,
    storage_prefix="source_items/catalogue",
)
_SPECS = [_BOUGHT, _MADE, _SOURCE]
_SPEC_IDS = [s.id for s in _SPECS]
# STEP/MESH exist on bought and made only (source is raw stock,
# no assembly geometry to attach).
_STEP_MESH_SPECS = [_BOUGHT, _MADE]
_STEP_MESH_IDS = ["bought", "made"]


def _make_file(spec: _KindSpec, **overrides: Any) -> Any:
    item_id = overrides.pop("item_id", 1)
    fields: dict[str, Any] = dict(
        id=1,
        file_name="f.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_path=f"{spec.storage_prefix}/{item_id}/pdf/stored.pdf",
        sha256="a" * 64,
        category=spec.category.PDF,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )
    fields[spec.fk_field] = item_id
    fields.update(overrides)
    return spec.file_entity(**fields)


# ── Get ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _SPECS, ids=_SPEC_IDS)
class TestGetItemFiles:
    async def test_unknown_item_raises_the_kind_specific_not_found_error(
        self, spec: _KindSpec
    ) -> None:
        uc = spec.get_uc(
            item_repo=_FakeItemRepo(exists=False), file_repo=_FakeFileRepo(), storage=None
        )
        with pytest.raises(spec.item_not_found, match=rf"{spec.item_label} #7 not found\."):
            await uc.execute(item_id=7)

    async def test_item_with_no_files_returns_empty_list(self, spec: _KindSpec) -> None:
        uc = spec.get_uc(item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo(), storage=None)
        assert await uc.execute(item_id=1) == []

    async def test_url_is_populated_when_storage_is_present(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        storage = _RecordingStorage(objects={f.storage_path: (b"x", "application/pdf")})
        uc = spec.get_uc(item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo([f]), storage=storage)
        [result] = await uc.execute(item_id=1)
        assert result.url == f"https://storage.test/{f.storage_path}"

    async def test_url_is_none_when_storage_is_disabled(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        uc = spec.get_uc(item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo([f]), storage=None)
        [result] = await uc.execute(item_id=1)
        assert result.url is None

    async def test_execute_many_tolerates_files_from_several_items_without_raising(
        self, spec: _KindSpec
    ) -> None:
        files = [_make_file(spec, id=1, item_id=1), _make_file(spec, id=2, item_id=2)]
        uc = spec.get_uc(item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo(files), storage=None)
        results = await uc.execute_many(item_ids=[1, 2, 999])
        assert {r.id for r in results} == {1, 2}


# ── Upload ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _SPECS, ids=_SPEC_IDS)
class TestUploadItemFile:
    async def test_rejects_when_storage_is_disabled(self, spec: _KindSpec) -> None:
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo(), storage=None, uow=FakeUnitOfWork()
        )
        with pytest.raises(StorageNotEnabledError):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=b"x",
                file_name="f.pdf",
                content_type="application/pdf",
                category=spec.category.PDF,
            )

    async def test_rejects_an_unknown_item(self, spec: _KindSpec) -> None:
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(exists=False),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(spec.item_not_found, match=rf"{spec.item_label} #1 not found\."):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=b"x",
                file_name="f.pdf",
                content_type="application/pdf",
                category=spec.category.PDF,
            )

    async def test_pdf_at_exact_size_limit_is_accepted(self, spec: _KindSpec) -> None:
        limit = 50 * 1024 * 1024
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        result = await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"x" * limit,
            file_name="f.pdf",
            content_type="application/pdf",
            category=spec.category.PDF,
        )
        assert result.size_bytes == limit

    async def test_pdf_over_size_limit_is_rejected_with_the_mb_figure(
        self, spec: _KindSpec
    ) -> None:
        over = 50 * 1024 * 1024 + 1
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(spec.too_large, match=r"pdf files must be ≤ 50 MB \(got \d+ bytes\)\."):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=b"x" * over,
                file_name="f.pdf",
                content_type="application/pdf",
                category=spec.category.PDF,
            )

    async def test_an_image_is_no_file_category(self, spec: _KindSpec) -> None:
        """Pictures are ItemPictures, not files, so an image sent for a file
        category is refused like any other non-PDF."""
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        assert not {"image", "thumbnail"} & {c.value for c in spec.category}
        with pytest.raises(spec.invalid_type, match=r"application/pdf"):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=_jpeg_bytes(),
                file_name="f.jpg",
                content_type="image/jpeg",
                category=spec.category.PDF,
            )

    async def test_singleton_category_deletes_the_old_storage_object_after_uploading_the_new_one(
        self, spec: _KindSpec
    ) -> None:
        old = _make_file(spec, id=1, category=spec.category.MESH, storage_path="old/path.stl")
        storage = _RecordingStorage(objects={old.storage_path: (b"old", "model/stl")})
        file_repo = _FakeFileRepo([old])
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(), file_repo=file_repo, storage=storage, uow=FakeUnitOfWork()
        )

        await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"solid new",
            file_name="new.stl",
            content_type="model/stl",
            category=spec.category.MESH,
        )

        delete_index = storage.calls.index(f"delete:{old.storage_path}")
        upload_index = next(i for i, c in enumerate(storage.calls) if c.startswith("upload:"))
        assert upload_index < delete_index
        assert old in file_repo.deleted
        # Exactly one MESH survives: the old row was replaced, not
        # kept alongside the new one.
        assert len([f for f in file_repo.files if f.category == spec.category.MESH]) == 1

    async def test_read_transaction_ends_before_the_image_work_and_upload(
        self, spec: _KindSpec
    ) -> None:
        log: list[str] = []
        storage = _RecordingStorage()
        storage.calls = log
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_SequencedFileRepo(log),
            storage=storage,
            uow=_RecordingUow(log),
        )

        await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"solid new",
            file_name="new.stl",
            content_type="model/stl",
            category=spec.category.MESH,
        )

        assert log[0] == "commit"
        assert log[1].startswith("upload:")
        assert log[2:4] == ["save:1", "commit"]

    async def test_replaced_singleton_is_removed_only_after_the_new_row_is_saved(
        self, spec: _KindSpec
    ) -> None:
        log: list[str] = []
        old = _make_file(spec, id=1, category=spec.category.MESH, storage_path="old/path.stl")
        storage = _RecordingStorage(objects={old.storage_path: (b"old", "model/stl")})
        storage.calls = log
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_SequencedFileRepo(log, [old]),
            storage=storage,
            uow=_RecordingUow(log),
        )

        await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"solid new",
            file_name="new.stl",
            content_type="model/stl",
            category=spec.category.MESH,
        )

        # The new row and the removal of the old one commit together, and the
        # old blob goes only after that commit has succeeded.
        writes = [c for c in log if not c.startswith("get_url:")]
        assert writes[0] == "commit"
        assert writes[1].startswith("upload:")
        assert writes[2:] == ["save:2", "delete_row:1", "commit", f"delete:{old.storage_path}"]

    async def test_failed_commit_deletes_the_new_blob_and_keeps_the_old_one(
        self, spec: _KindSpec
    ) -> None:
        log: list[str] = []
        old = _make_file(spec, id=1, category=spec.category.MESH, storage_path="old/path.stl")
        storage = _RecordingStorage(objects={old.storage_path: (b"old", "model/stl")})
        storage.calls = log
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_SequencedFileRepo(log, [old]),
            storage=storage,
            uow=_RecordingUow(log, fail_commit_number=2),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=b"solid new",
                file_name="new.stl",
                content_type="model/stl",
                category=spec.category.MESH,
            )

        uploaded = log[1].removeprefix("upload:")
        assert log[2:] == ["save:2", "delete_row:1", "commit:failed", f"delete:{uploaded}"]
        assert list(storage.objects) == [old.storage_path]

    async def test_failed_save_deletes_the_new_blob_and_keeps_the_old_file(
        self, spec: _KindSpec
    ) -> None:
        log: list[str] = []
        old = _make_file(spec, id=1, category=spec.category.MESH, storage_path="old/path.stl")
        storage = _RecordingStorage(objects={old.storage_path: (b"old", "model/stl")})
        storage.calls = log
        file_repo = _SequencedFileRepo(log, [old], fail_save=True)
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(), file_repo=file_repo, storage=storage, uow=FakeUnitOfWork()
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=b"solid new",
                file_name="new.stl",
                content_type="model/stl",
                category=spec.category.MESH,
            )

        uploaded = log[0].removeprefix("upload:")
        assert log == [f"upload:{uploaded}", "save:failed", f"delete:{uploaded}"]
        assert list(storage.objects) == [old.storage_path]
        assert file_repo.files == [old]
        assert file_repo.deleted == []

    async def test_non_singleton_category_keeps_previously_uploaded_files(
        self, spec: _KindSpec
    ) -> None:
        existing = _make_file(spec, id=1, category=spec.category.PDF)
        file_repo = _FakeFileRepo([existing])
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=file_repo,
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )

        await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"new pdf",
            file_name="new.pdf",
            content_type="application/pdf",
            category=spec.category.PDF,
        )

        assert len([f for f in file_repo.files if f.category == spec.category.PDF]) == 2
        assert existing not in file_repo.deleted

    async def test_result_carries_a_resolved_storage_url(self, spec: _KindSpec) -> None:
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        result = await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"x",
            file_name="f.pdf",
            content_type="application/pdf",
            category=spec.category.PDF,
        )
        assert result.url is not None
        assert result.url.startswith("https://storage.test/")


# ── STEP / MESH (bought and made only) ──────────────────────────────


@pytest.mark.parametrize("spec", _STEP_MESH_SPECS, ids=_STEP_MESH_IDS)
class TestStepAndMeshCategories:
    async def test_step_rejects_a_non_step_extension(self, spec: _KindSpec) -> None:
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(spec.invalid_type, match=r"STEP files must have a \.step or \.stp"):
            await uc.execute(
                actor=_writer(spec.write_permission),
                item_id=1,
                data=b"x",
                file_name="part.iges",
                content_type="application/octet-stream",
                category=spec.category.STEP,
            )

    async def test_step_accepts_the_stp_extension(self, spec: _KindSpec) -> None:
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        result = await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"x",
            file_name="part.stp",
            content_type="application/octet-stream",
            category=spec.category.STEP,
        )
        assert result.stored_name.endswith(".stp")

    async def test_mesh_pins_the_canonical_mime_from_the_extension_not_the_upload(
        self, spec: _KindSpec
    ) -> None:
        storage = _RecordingStorage()
        uc = spec.upload_uc(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=storage,
            uow=FakeUnitOfWork(),
        )
        result = await uc.execute(
            actor=_writer(spec.write_permission),
            item_id=1,
            data=b"solid x",
            file_name="part.3mf",
            content_type="application/octet-stream",
            category=spec.category.MESH,
        )
        assert result.mime_type == "model/3mf"


# ── DXF (made item only) ─────────────────────────────────────────────


class TestMadeItemDxfCategory:
    async def test_rejects_a_non_dxf_extension(self) -> None:
        uc = UploadMadeItemFile(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(MadeItemFileInvalidTypeError, match=r"DXF files must have a \.dxf"):
            await uc.execute(
                actor=_writer(Permission.WRITE_MADE_ITEMS),
                item_id=1,
                data=b"x",
                file_name="drawing.dwg",
                content_type="application/octet-stream",
                category=MadeItemFileCategory.DXF,
            )

    async def test_accepts_the_dxf_extension(self) -> None:
        uc = UploadMadeItemFile(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        result = await uc.execute(
            actor=_writer(Permission.WRITE_MADE_ITEMS),
            item_id=1,
            data=b"x",
            file_name="drawing.dxf",
            content_type="application/octet-stream",
            category=MadeItemFileCategory.DXF,
        )
        assert result.stored_name.endswith(".dxf")


# ── The PDF-content-type-mismatch message: a real wording divergence ──


class TestPdfFallbackMessageWording:
    """Verification of divergences: bought/source hardcode "PDF category requires
    ..." (their only fallback-reaching category IS pdf); made's fallback
    covers both PDF and DRAWING and is genuinely dynamic
    ("{category} category requires..."). For made's own PDF category this
    produces "pdf category ..." (lowercase, from category.value), a
    DIFFERENT string than bought/source's hardcoded "PDF category ..."
    for the textually same situation. A shared implementation must
    reproduce this exactly, not quietly unify it."""

    async def test_bought_pdf_mismatch_message_is_the_hardcoded_capitalised_form(self) -> None:
        uc = UploadBoughtItemFile(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(
            BoughtItemFileInvalidTypeError,
            match=r"^PDF category requires application/pdf content type \(got 'text/plain'\)\.$",
        ):
            await uc.execute(
                actor=_writer(Permission.WRITE_BOUGHT_ITEMS),
                item_id=1,
                data=b"x",
                file_name="f.pdf",
                content_type="text/plain",
                category=BoughtItemFileCategory.PDF,
            )

    async def test_source_pdf_mismatch_message_is_the_hardcoded_capitalised_form(self) -> None:
        uc = UploadSourceItemFile(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(
            SourceItemFileInvalidTypeError,
            match=r"^PDF category requires application/pdf content type \(got 'text/plain'\)\.$",
        ):
            await uc.execute(
                actor=_writer(Permission.WRITE_SOURCE_ITEMS),
                item_id=1,
                data=b"x",
                file_name="f.pdf",
                content_type="text/plain",
                category=SourceItemFileCategory.PDF,
            )

    async def test_made_pdf_mismatch_message_uses_the_dynamic_lowercase_form(self) -> None:
        uc = UploadMadeItemFile(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(
            MadeItemFileInvalidTypeError,
            match=r"^pdf category requires application/pdf content type \(got 'text/plain'\)\.$",
        ):
            await uc.execute(
                actor=_writer(Permission.WRITE_MADE_ITEMS),
                item_id=1,
                data=b"x",
                file_name="f.pdf",
                content_type="text/plain",
                category=MadeItemFileCategory.PDF,
            )

    async def test_made_drawing_mismatch_message_names_drawing_not_pdf(self) -> None:
        uc = UploadMadeItemFile(
            item_repo=_FakeItemRepo(),
            file_repo=_FakeFileRepo(),
            storage=_RecordingStorage(),
            uow=FakeUnitOfWork(),
        )
        with pytest.raises(
            MadeItemFileInvalidTypeError,
            match=(
                r"^drawing category requires application/pdf content type "
                r"\(got 'text/plain'\)\.$"
            ),
        ):
            await uc.execute(
                actor=_writer(Permission.WRITE_MADE_ITEMS),
                item_id=1,
                data=b"x",
                file_name="f.pdf",
                content_type="text/plain",
                category=MadeItemFileCategory.DRAWING,
            )


# ── Update ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _SPECS, ids=_SPEC_IDS)
class TestUpdateItemFile:
    async def test_renames_the_file_and_returns_the_new_name(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        uc = spec.update_uc(file_repo=_FakeFileRepo([f]), storage=None, uow=FakeUnitOfWork())
        result = await uc.execute(
            actor=_writer(spec.write_permission),
            file_id=f.id,
            command=spec.update_command(file_name="renamed.pdf"),
        )
        assert result.file_name == "renamed.pdf"

    async def test_missing_file_raises_not_found_with_a_kind_agnostic_message(
        self, spec: _KindSpec
    ) -> None:
        uc = spec.update_uc(file_repo=_FakeFileRepo(), storage=None, uow=FakeUnitOfWork())
        with pytest.raises(spec.file_not_found, match=r"^File #99 not found\.$"):
            await uc.execute(
                actor=_writer(spec.write_permission),
                file_id=99,
                command=spec.update_command(file_name="x.pdf"),
            )

    async def test_url_is_none_when_storage_is_disabled(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        uc = spec.update_uc(file_repo=_FakeFileRepo([f]), storage=None, uow=FakeUnitOfWork())
        result = await uc.execute(
            actor=_writer(spec.write_permission),
            file_id=f.id,
            command=spec.update_command(file_name="x.pdf"),
        )
        assert result.url is None


# ── Delete ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _SPECS, ids=_SPEC_IDS)
class TestDeleteItemFile:
    async def test_removes_the_storage_object_only_after_the_row_deletion_commits(
        self, spec: _KindSpec
    ) -> None:
        log: list[str] = []
        f = _make_file(spec)
        storage = _RecordingStorage(objects={f.storage_path: (b"x", "application/pdf")})
        storage.calls = log
        file_repo = _SequencedFileRepo(log, [f])
        uc = spec.delete_uc(file_repo=file_repo, storage=storage, uow=_RecordingUow(log))

        await uc.execute(actor=_writer(spec.write_permission), file_id=f.id)

        assert log == [f"delete_row:{f.id}", "commit", f"delete:{f.storage_path}"]
        assert f in file_repo.deleted
        assert file_repo.files == []

    async def test_failed_commit_keeps_the_storage_object(self, spec: _KindSpec) -> None:
        log: list[str] = []
        f = _make_file(spec)
        storage = _RecordingStorage(objects={f.storage_path: (b"x", "application/pdf")})
        storage.calls = log
        uc = spec.delete_uc(
            file_repo=_SequencedFileRepo(log, [f]),
            storage=storage,
            uow=_RecordingUow(log, fail_commit_number=1),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await uc.execute(actor=_writer(spec.write_permission), file_id=f.id)

        assert log == [f"delete_row:{f.id}", "commit:failed"]
        assert f.storage_path in storage.objects

    async def test_failed_storage_delete_after_commit_is_logged_not_raised(
        self, spec: _KindSpec, glados_caplog: pytest.LogCaptureFixture
    ) -> None:
        f = _make_file(spec)
        file_repo = _FakeFileRepo([f])
        uc = spec.delete_uc(
            file_repo=file_repo, storage=_FailingDeleteStorage(), uow=FakeUnitOfWork()
        )

        await uc.execute(actor=_writer(spec.write_permission), file_id=f.id)

        assert file_repo.files == []
        assert any(
            r.levelname == "WARNING" and f.storage_path in r.getMessage()
            for r in glados_caplog.records
        )

    async def test_missing_file_raises_not_found(self, spec: _KindSpec) -> None:
        uc = spec.delete_uc(
            file_repo=_FakeFileRepo(), storage=_RecordingStorage(), uow=FakeUnitOfWork()
        )
        with pytest.raises(spec.file_not_found, match=r"^File #7 not found\.$"):
            await uc.execute(actor=_writer(spec.write_permission), file_id=7)

    async def test_disabled_storage_still_deletes_the_row(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        file_repo = _FakeFileRepo([f])
        uc = spec.delete_uc(file_repo=file_repo, storage=None, uow=FakeUnitOfWork())

        await uc.execute(actor=_writer(spec.write_permission), file_id=f.id)

        assert f in file_repo.deleted


# The order, product and production order deletes do not share the base
# class but promise the same order, so they are pinned here too.


class _FakeProductRepo:
    async def get_by_id(self, id: int) -> Any:
        return SimpleNamespace(id=id, designated_user_id=None, product_number="P-1")


def _delete_order_file(file_repo: Any, storage: Any, uow: Any) -> Any:
    return DeleteOrderFile(file_repo=file_repo, storage=storage, uow=uow)


def _delete_product_file(file_repo: Any, storage: Any, uow: Any) -> Any:
    return DeleteProductFile(
        product_repo=_FakeProductRepo(), file_repo=file_repo, storage=storage, uow=uow
    )


class _LockingOrderRepo:
    """Records the production orders a delete locks."""

    def __init__(self, log: list[str] | None = None) -> None:
        self._log = log

    async def lock_for_update(self, ids: list[int]) -> None:
        if self._log is not None:
            self._log.extend(f"lock_order:{i}" for i in ids)


def _delete_production_order_file(file_repo: Any, storage: Any, uow: Any) -> Any:
    return DeleteProductionOrderFile(
        file_repo=file_repo, storage=storage, order_repo=_LockingOrderRepo(), uow=uow
    )


_OTHER_DELETES = [
    (_delete_order_file, Permission.WRITE_ORDERS),
    (_delete_product_file, Permission.MANAGE_PROJECTS),
    (_delete_production_order_file, Permission.WRITE_INSPECTIONS),
]
_OTHER_DELETE_IDS = ["order", "product", "production_order"]


@pytest.mark.parametrize(("build", "permission"), _OTHER_DELETES, ids=_OTHER_DELETE_IDS)
class TestDeleteOtherFileKinds:
    async def test_removes_the_storage_object_only_after_the_row_deletion_commits(
        self, build: Any, permission: str
    ) -> None:
        log: list[str] = []
        f = SimpleNamespace(
            id=1,
            product_id=1,
            production_order_id=1,
            delivery_id=None,
            file_name="f.pdf",
            storage_path="kind/1/f.pdf",
        )
        storage = _RecordingStorage(objects={f.storage_path: (b"x", "application/pdf")})
        storage.calls = log
        uc = build(_SequencedFileRepo(log, [f]), storage, _RecordingUow(log))

        await uc.execute(actor=_writer(permission), file_id=f.id)

        assert log == [f"delete_row:{f.id}", "commit", f"delete:{f.storage_path}"]

    async def test_failed_commit_keeps_the_storage_object(
        self, build: Any, permission: str
    ) -> None:
        log: list[str] = []
        f = SimpleNamespace(
            id=1,
            product_id=1,
            production_order_id=1,
            delivery_id=None,
            file_name="f.pdf",
            storage_path="kind/1/f.pdf",
        )
        storage = _RecordingStorage(objects={f.storage_path: (b"x", "application/pdf")})
        storage.calls = log
        uc = build(_SequencedFileRepo(log, [f]), storage, _RecordingUow(log, fail_commit_number=1))

        with pytest.raises(RuntimeError, match="database unavailable"):
            await uc.execute(actor=_writer(permission), file_id=f.id)

        assert log == [f"delete_row:{f.id}", "commit:failed"]
        assert f.storage_path in storage.objects


async def test_production_order_evidence_delete_locks_its_order_first() -> None:
    """A completion checks for evidence under the production order's lock, so
    the delete takes that lock before it removes the row."""
    log: list[str] = []
    f = SimpleNamespace(
        id=1, production_order_id=7, file_name="f.pdf", storage_path="production_orders/7/f.pdf"
    )
    storage = _RecordingStorage(objects={f.storage_path: (b"x", "application/pdf")})
    uc = DeleteProductionOrderFile(
        file_repo=_SequencedFileRepo(log, [f]),
        storage=storage,
        order_repo=_LockingOrderRepo(log),
        uow=_RecordingUow(log),
    )

    await uc.execute(actor=_writer(Permission.WRITE_INSPECTIONS), file_id=f.id)

    assert log == ["lock_order:7", f"delete_row:{f.id}", "commit"]


# ── Download ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _SPECS, ids=_SPEC_IDS)
class TestDownloadItemFile:
    async def test_returns_bytes_and_content_type_from_storage(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        storage = _RecordingStorage(objects={f.storage_path: (b"pdf-bytes", "application/pdf")})
        uc = spec.download_uc(file_repo=_FakeFileRepo([f]), storage=storage)

        file, data, content_type = await uc.execute(item_id=1, file_id=f.id)

        assert data == b"pdf-bytes"
        assert content_type == "application/pdf"
        assert file.id == f.id

    async def test_read_transaction_ends_before_the_storage_download(self, spec: _KindSpec) -> None:
        log: list[str] = []
        f = _make_file(spec)
        storage = _RecordingStorage(objects={f.storage_path: (b"pdf-bytes", "application/pdf")})
        storage.calls = log
        uc = spec.download_uc(file_repo=_FakeFileRepo([f]), storage=storage, uow=_RecordingUow(log))

        await uc.execute(item_id=1, file_id=f.id)

        assert log == ["commit", f"download:{f.storage_path}"]

    async def test_disabled_storage_raises(self, spec: _KindSpec) -> None:
        f = _make_file(spec)
        uc = spec.download_uc(file_repo=_FakeFileRepo([f]), storage=None)
        with pytest.raises(StorageNotEnabledError):
            await uc.execute(item_id=1, file_id=f.id)

    async def test_missing_file_raises_not_found(self, spec: _KindSpec) -> None:
        uc = spec.download_uc(file_repo=_FakeFileRepo(), storage=_RecordingStorage())
        with pytest.raises(spec.file_not_found, match=r"^File #5 not found\.$"):
            await uc.execute(item_id=1, file_id=5)

    async def test_a_file_belonging_to_another_item_404s_not_403s(self, spec: _KindSpec) -> None:
        f = _make_file(spec, item_id=1)
        uc = spec.download_uc(file_repo=_FakeFileRepo([f]), storage=_RecordingStorage())
        with pytest.raises(spec.file_not_found):
            await uc.execute(item_id=999, file_id=f.id)
