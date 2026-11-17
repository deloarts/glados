"""
Transaction and storage ordering for the order, product and production order
file uploads. Each one ends the read transaction before hashing and storing
the bytes, stores the blob before writing its row, commits the row through
its unit of work, and deletes that blob again when the row cannot be saved.
The product upload also replaces a singleton category, so its old row goes
in the same commit as the new row and its old blob only after that commit.
The bought/made/source item uploads are covered in test_item_file_behaviour.py.
"""

import io
from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from src.modules.fulfillment.application.use_cases.order.upload_order_file import UploadOrderFile
from src.modules.fulfillment.application.use_cases.production_order.upload_production_order_file import (
    UploadProductionOrderFile,
)
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.workspace.application.use_cases.product.upload_product_file import (
    UploadProductFile,
)
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from tests.unit.fakes import FakeUnitOfWork


def _user(permissions: list[str]) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=permissions,
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


class _ParentRepo:
    def __init__(self, parent: Any) -> None:
        self._parent = parent

    async def get_by_id(self, id: int) -> Any:
        return self._parent


class _SequencedFileRepo:
    def __init__(self, log: list[str], files: list[Any] | None = None, fail_save: bool = False):
        self._log = log
        self.files: list[Any] = list(files or [])
        self._fail_save = fail_save

    async def get_by_item_id_and_category(self, item_id: int, category: Any) -> list[Any]:
        return [f for f in self.files if f.category == category]

    async def save(self, file: Any) -> Any:
        if self._fail_save:
            self._log.append("save:failed")
            raise RuntimeError("database unavailable")
        file.id = max((f.id for f in self.files), default=0) + 1
        self.files.append(file)
        self._log.append(f"save:{file.id}")
        return file

    async def delete(self, file: Any) -> None:
        self._log.append(f"delete_row:{file.id}")
        self.files = [f for f in self.files if f.id != file.id]


class _SequencedStorage:
    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.objects: set[str] = set()

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._log.append(f"upload:{key}")
        self.objects.add(key)

    async def delete(self, key: str) -> None:
        self._log.append(f"delete:{key}")
        self.objects.discard(key)

    def get_url(self, key: str, file_name: str | None = None) -> str:
        return f"https://storage.test/{key}"


class _RecordingUow:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


def _order_upload(log: list[str], repo: _SequencedFileRepo, uow: Any) -> Any:
    storage = _SequencedStorage(log)
    uc = UploadOrderFile(
        order_repo=_ParentRepo(object()),
        file_repo=repo,
        storage=storage,
        uow=uow,
    )
    return storage, uc.execute(
        actor=_user([Permission.WRITE_ORDERS]),
        order_id=1,
        data=b"%PDF-1.7",
        file_name="note.pdf",
        content_type="application/pdf",
        category=OrderFileCategory.DELIVERY_NOTE,
    )


def _production_order_upload(log: list[str], repo: _SequencedFileRepo, uow: Any) -> Any:
    storage = _SequencedStorage(log)
    uc = UploadProductionOrderFile(
        order_repo=_ParentRepo(object()),
        file_repo=repo,
        storage=storage,
        uow=uow,
    )
    return storage, uc.execute(
        actor=_user([Permission.WRITE_INSPECTIONS]),
        order_id=1,
        data=b"%PDF-1.7",
        file_name="report.pdf",
        content_type="application/pdf",
        category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
    )


def _product_upload(log: list[str], repo: _SequencedFileRepo, uow: Any) -> Any:
    product = SimpleNamespace(id=1, designated_user_id=None, product_number="P-1")
    storage = _SequencedStorage(log)
    uc = UploadProductFile(
        product_repo=_ParentRepo(product),
        file_repo=repo,
        storage=storage,
        uow=uow,
    )
    return storage, uc.execute(
        actor=_user([Permission.MANAGE_PROJECTS]),
        product_id=1,
        data=b"%PDF-1.7",
        file_name="sheet.pdf",
        content_type="application/pdf",
        category=ProductFileCategory.PDF,
    )


_UPLOADS = [
    pytest.param(_order_upload, id="order"),
    pytest.param(_production_order_upload, id="production-order"),
    pytest.param(_product_upload, id="product"),
]


@pytest.mark.parametrize("start_upload", _UPLOADS)
async def test_commits_before_the_upload_and_uploads_before_the_save(start_upload: Any) -> None:
    log: list[str] = []
    _, run = start_upload(log, _SequencedFileRepo(log), _RecordingUow(log))

    await run

    assert log[0] == "commit"
    assert log[1].startswith("upload:")
    assert log[2:] == ["save:1", "commit"]


@pytest.mark.parametrize("start_upload", _UPLOADS)
async def test_failed_save_deletes_the_new_blob_and_reraises(start_upload: Any) -> None:
    log: list[str] = []
    storage, run = start_upload(log, _SequencedFileRepo(log, fail_save=True), FakeUnitOfWork())

    with pytest.raises(RuntimeError, match="database unavailable"):
        await run

    uploaded = log[0].removeprefix("upload:")
    assert log == [f"upload:{uploaded}", "save:failed", f"delete:{uploaded}"]
    assert storage.objects == set()


def _product_thumbnail(id: int, storage_path: str) -> ProductFile:
    return ProductFile(
        id=id,
        product_id=1,
        file_name="old.png",
        stored_name="old.png",
        mime_type="image/png",
        size_bytes=3,
        storage_path=storage_path,
        sha256="a" * 64,
        category=ProductFileCategory.THUMBNAIL,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


async def _upload_product_thumbnail(
    log: list[str], repo: _SequencedFileRepo, storage: _SequencedStorage
) -> None:
    product = SimpleNamespace(id=1, designated_user_id=None, product_number="P-1")
    uc = UploadProductFile(
        product_repo=_ParentRepo(product),
        file_repo=repo,
        storage=storage,
        uow=_RecordingUow(log),
    )
    await uc.execute(
        actor=_user([Permission.MANAGE_PROJECTS]),
        product_id=1,
        data=_jpeg_bytes(),
        file_name="new.jpg",
        content_type="image/jpeg",
        category=ProductFileCategory.THUMBNAIL,
    )


async def test_product_singleton_is_replaced_only_after_the_new_row_is_saved() -> None:
    log: list[str] = []
    old = _product_thumbnail(1, "products/1/thumbnail/old.png")
    storage = _SequencedStorage(log)
    storage.objects.add(old.storage_path)

    await _upload_product_thumbnail(log, _SequencedFileRepo(log, [old]), storage)

    # The new row and the removal of the old one commit together, and the
    # old blob goes only after that commit has succeeded.
    assert log[0] == "commit"
    assert log[1].startswith("upload:")
    assert log[2:] == ["save:2", "delete_row:1", "commit", f"delete:{old.storage_path}"]


async def test_product_singleton_keeps_the_old_file_when_the_save_fails() -> None:
    log: list[str] = []
    old = _product_thumbnail(1, "products/1/thumbnail/old.png")
    storage = _SequencedStorage(log)
    storage.objects.add(old.storage_path)
    repo = _SequencedFileRepo(log, [old], fail_save=True)

    with pytest.raises(RuntimeError):
        await _upload_product_thumbnail(log, repo, storage)

    assert storage.objects == {old.storage_path}
    assert repo.files == [old]
