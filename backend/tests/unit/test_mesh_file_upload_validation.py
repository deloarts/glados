"""
The MESH slot on bought and made items takes either .stl or .3mf. Two
things are worth pinning down: the extension
whitelist (it is the *only* gate, the content type a browser sends for a
mesh is not trustworthy), and the canonical mime the use case writes back,
since that is what tells a consumer which of the two formats the slot
currently holds.
"""

import uuid
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.use_cases.bought_item._file_kind import BOUGHT_ITEM_FILE_KIND
from src.modules.catalogue.application.use_cases.made_item._file_kind import MADE_ITEM_FILE_KIND
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.domain.errors import BoughtItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import MadeItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import MadeItemFileTooLargeError
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
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
        ("part.stl", ".stl"),
        ("part.3mf", ".3mf"),
        ("PART.STL", ".stl"),
        ("PART.3MF", ".3mf"),
        ("archive.tar.3mf", ".3mf"),
    ],
)
def test_mesh_accepts_stl_and_3mf(file_name: str, expected_ext: str) -> None:
    assert (
        MADE_ITEM_FILE_KIND.validate_upload(MadeItemFileCategory.MESH, "", file_name, 10)
        == expected_ext
    )
    assert (
        BOUGHT_ITEM_FILE_KIND.validate_upload(BoughtItemFileCategory.MESH, "", file_name, 10)
        == expected_ext
    )


@pytest.mark.parametrize("file_name", ["part.obj", "part.step", "part", "part.3mf.zip"])
def test_mesh_rejects_other_extensions(file_name: str) -> None:
    with pytest.raises(MadeItemFileInvalidTypeError):
        MADE_ITEM_FILE_KIND.validate_upload(MadeItemFileCategory.MESH, "", file_name, 10)
    with pytest.raises(BoughtItemFileInvalidTypeError):
        BOUGHT_ITEM_FILE_KIND.validate_upload(BoughtItemFileCategory.MESH, "", file_name, 10)


def test_mesh_content_type_is_ignored_in_favour_of_the_extension() -> None:
    # Browsers routinely send octet-stream (or nothing) for both formats.
    assert (
        MADE_ITEM_FILE_KIND.validate_upload(
            MadeItemFileCategory.MESH, "application/octet-stream", "p.3mf", 10
        )
        == ".3mf"
    )


def test_3mf_shares_the_stl_size_limit() -> None:
    over = 100 * 1024 * 1024 + 1
    with pytest.raises(MadeItemFileTooLargeError):
        MADE_ITEM_FILE_KIND.validate_upload(MadeItemFileCategory.MESH, "", "p.3mf", over)


# ── canonical mime written back on upload ─────────────────────────────


class _FakeItemRepo:
    async def get_by_id(self, item_id: int) -> object:
        return object()


class _FakeFileRepo:
    async def get_by_item_id_and_category(self, item_id: int, category: object) -> list:
        return []

    async def save(self, record):
        record.id = 1
        record.public_id = uuid.uuid4()
        return record


class _FakeStorage:
    def __init__(self) -> None:
        self.uploaded_content_type: str | None = None

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.uploaded_content_type = content_type

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
        permissions=[Permission.WRITE_MADE_ITEMS],
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
    [("part.stl", "model/stl"), ("part.3mf", "model/3mf")],
)
async def test_upload_pins_the_canonical_mesh_mime(file_name: str, expected_mime: str) -> None:
    storage = _FakeStorage()
    uc = UploadMadeItemFile(
        item_repo=_FakeItemRepo(), file_repo=_FakeFileRepo(), storage=storage, uow=FakeUnitOfWork()
    )

    result = await uc.execute(
        actor=_writer(),
        item_id=1,
        data=b"solid x",
        file_name=file_name,
        content_type="application/octet-stream",
        category=MadeItemFileCategory.MESH,
    )

    assert result.mime_type == expected_mime
    assert storage.uploaded_content_type == expected_mime
