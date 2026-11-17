"""
Source items share the MESH singleton with bought/made items (a
source item can still carry a 3D mesh of the stock shape, even though it
has no STEP/assembly-CAD category, see source_item_file_category.py's
docstring). This mirrors tests/unit/test_mesh_file_upload_validation.py's
coverage of bought/made's MESH slot, plus the singleton-replace behaviour
tests/unit/test_item_file_behaviour.py already pins generically for
THUMBNAIL/IMAGE on all three kinds.
"""

import uuid
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.use_cases.source_item._file_kind import SOURCE_ITEM_FILE_KIND
from src.modules.catalogue.application.use_cases.source_item.upload_source_item_file import (
    UploadSourceItemFile,
)
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.errors import SourceItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import SourceItemFileTooLargeError
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit.fakes import FakeUnitOfWork

# ── extension whitelist ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("file_name", "expected_ext"),
    [
        ("stock.stl", ".stl"),
        ("stock.3mf", ".3mf"),
        ("STOCK.STL", ".stl"),
        ("STOCK.3MF", ".3mf"),
        ("archive.tar.3mf", ".3mf"),
    ],
)
def test_source_mesh_accepts_stl_and_3mf(file_name: str, expected_ext: str) -> None:
    assert (
        SOURCE_ITEM_FILE_KIND.validate_upload(SourceItemFileCategory.MESH, "", file_name, 10)
        == expected_ext
    )


@pytest.mark.parametrize("file_name", ["stock.obj", "stock.step", "stock", "stock.3mf.zip"])
def test_source_mesh_rejects_other_extensions(file_name: str) -> None:
    with pytest.raises(SourceItemFileInvalidTypeError):
        SOURCE_ITEM_FILE_KIND.validate_upload(SourceItemFileCategory.MESH, "", file_name, 10)


def test_source_mesh_content_type_is_ignored_in_favour_of_the_extension() -> None:
    # Browsers routinely send octet-stream (or nothing) for both formats.
    assert (
        SOURCE_ITEM_FILE_KIND.validate_upload(
            SourceItemFileCategory.MESH, "application/octet-stream", "s.3mf", 10
        )
        == ".3mf"
    )


def test_source_mesh_shares_the_bought_made_size_limit() -> None:
    over = 100 * 1024 * 1024 + 1
    with pytest.raises(SourceItemFileTooLargeError):
        SOURCE_ITEM_FILE_KIND.validate_upload(SourceItemFileCategory.MESH, "", "s.3mf", over)


def test_source_mesh_is_a_singleton() -> None:
    assert SourceItemFileCategory.MESH.is_singleton()


# ── canonical mime written back on upload, and singleton replacement ──


class _FakeItemRepo:
    async def get_by_id(self, item_id: int) -> object:
        return object()


class _FakeFileRepo:
    def __init__(self, files: list | None = None) -> None:
        self.files: list = list(files or [])
        self.deleted: list = []

    async def get_by_item_id_and_category(self, item_id: int, category: object) -> list:
        return [f for f in self.files if f.category == category]

    async def save(self, record):
        if record.id == 0:
            record.id = len(self.files) + 1
            record.public_id = uuid.uuid4()
            self.files.append(record)
        return record

    async def delete(self, record):
        self.deleted.append(record)
        self.files = [f for f in self.files if f is not record]


class _FakeStorage:
    def __init__(self) -> None:
        self.uploaded_content_type: str | None = None
        self.calls: list[str] = []

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.calls.append(f"upload:{path}")
        self.uploaded_content_type = content_type

    async def delete(self, path: str) -> None:
        self.calls.append(f"delete:{path}")

    def get_url(self, path: str, file_name: str | None = None) -> str:
        return f"https://example.test/{path}"


def _writer() -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=[Permission.WRITE_SOURCE_ITEMS],
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


@pytest.mark.parametrize(
    ("file_name", "expected_mime"),
    [("stock.stl", "model/stl"), ("stock.3mf", "model/3mf")],
)
async def test_source_upload_pins_the_canonical_mesh_mime(
    file_name: str, expected_mime: str
) -> None:
    storage = _FakeStorage()
    uc = UploadSourceItemFile(
        item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo(), storage=storage, uow=FakeUnitOfWork()
    )

    result = await uc.execute(
        actor=_writer(),
        item_id=1,
        data=b"solid x",
        file_name=file_name,
        content_type="application/octet-stream",
        category=SourceItemFileCategory.MESH,
    )

    assert result.mime_type == expected_mime
    assert storage.uploaded_content_type == expected_mime


async def test_source_mesh_upload_replaces_the_previous_mesh_singleton() -> None:
    old = SourceItemFile(
        id=1,
        source_item_id=1,
        file_name="old.stl",
        stored_name="old.stl",
        mime_type="model/stl",
        size_bytes=3,
        storage_path="source_items/catalogue/1/mesh/old.stl",
        sha256="a" * 64,
        category=SourceItemFileCategory.MESH,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )
    file_repo = _FakeFileRepo([old])
    storage = _FakeStorage()
    uc = UploadSourceItemFile(
        item_repo=_FakeItemRepo(), file_repo=file_repo, storage=storage, uow=FakeUnitOfWork()
    )

    await uc.execute(
        actor=_writer(),
        item_id=1,
        data=b"solid y",
        file_name="new.3mf",
        content_type="application/octet-stream",
        category=SourceItemFileCategory.MESH,
    )

    delete_index = storage.calls.index(f"delete:{old.storage_path}")
    upload_index = next(i for i, c in enumerate(storage.calls) if c.startswith("upload:"))
    assert upload_index < delete_index
    assert old in file_repo.deleted
    assert len([f for f in file_repo.files if f.category == SourceItemFileCategory.MESH]) == 1
