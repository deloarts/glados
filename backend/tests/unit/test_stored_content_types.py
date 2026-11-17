"""
Stored files reach a browser with the content type of their extension,
never the type the uploading client claimed, and a link to one downloads it
unless the type is safe to show inline. A STEP file labelled `text/html`
must not render as a page on the Glados origin.
"""

import uuid
from datetime import UTC
from datetime import datetime
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest

from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.platform.adapters.outbound.external.storage.azure_storage import (
    AzureStorageAdapter,
)
from src.modules.platform.adapters.outbound.external.storage.s3_storage import S3StorageAdapter
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.content_types import content_disposition
from src.modules.platform.domain.services.content_types import content_type_for
from src.modules.platform.domain.services.content_types import is_inline_safe
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit.fakes import FakeUnitOfWork

# ── the mapping ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("made_items/1/step/a.step", "model/step"),
        ("PART.STP", "model/step"),
        ("drawing.dxf", "application/dxf"),
        ("logo.svg", "image/svg+xml"),
        ("photo.JPEG", "image/jpeg"),
        ("doc.pdf", "application/pdf"),
        ("page.html", "application/octet-stream"),
        ("no-extension", "application/octet-stream"),
        ("dir.d/no-extension", "application/octet-stream"),
        (".stl", "model/stl"),
        ("archive.sql.gz.enc", "application/octet-stream"),
    ],
)
def test_content_type_follows_the_extension(name: str, expected: str) -> None:
    assert content_type_for(name) == expected


def test_only_raster_images_and_pdf_are_inline_safe() -> None:
    assert is_inline_safe("image/png")
    assert is_inline_safe("Application/PDF; charset=binary")
    assert not is_inline_safe("image/svg+xml")
    assert not is_inline_safe("text/html")
    assert not is_inline_safe("model/step")


def test_content_disposition_strips_line_breaks_and_encodes_the_name() -> None:
    value = content_disposition('Zeichnung "Ü"\r\nX-Evil: 1.pdf', inline=False)

    assert "\r" not in value and "\n" not in value
    assert value.startswith("attachment; filename=\"Zeichnung '?'X-Evil: 1.pdf\"")
    assert value.endswith("filename*=UTF-8''Zeichnung%20%22%C3%9C%22X-Evil%3A%201.pdf")
    assert content_disposition("a.png", inline=True).startswith("inline;")


# ── uploads store the type of the extension ───────────────────────────


class _ItemRepo:
    async def get_by_id(self, item_id: int) -> object:
        return object()


class _FileRepo:
    async def get_by_item_id_and_category(self, item_id: int, category: object) -> list:
        return []

    async def save(self, record):
        record.id = 1
        record.public_id = uuid.uuid4()
        return record


class _Storage:
    def __init__(self) -> None:
        self.uploaded_content_type: str | None = None
        self.url_file_name: str | None = None

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.uploaded_content_type = content_type

    def get_url(self, path: str, file_name: str | None = None) -> str:
        self.url_file_name = file_name
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
    ("file_name", "category", "expected"),
    [
        ("part.step", MadeItemFileCategory.STEP, "model/step"),
        ("part.stp", MadeItemFileCategory.STEP, "model/step"),
        ("part.dxf", MadeItemFileCategory.DXF, "application/dxf"),
    ],
)
async def test_an_upload_claiming_html_is_stored_as_its_extension(
    file_name: str, category: MadeItemFileCategory, expected: str
) -> None:
    storage = _Storage()
    uc = UploadMadeItemFile(
        item_repo=_ItemRepo(), file_repo=_FileRepo(), storage=storage, uow=FakeUnitOfWork()
    )

    result = await uc.execute(
        actor=_writer(),
        item_id=1,
        data=b"<script>alert(1)</script>",
        file_name=file_name,
        content_type="text/html",
        category=category,
    )

    assert result.mime_type == expected
    assert storage.uploaded_content_type == expected
    assert storage.url_file_name == file_name


# ── links to stored files ─────────────────────────────────────────────


def _s3() -> S3StorageAdapter:
    return S3StorageAdapter(
        bucket="objects",
        access_key="key",
        secret_key="secret",
        region="us-east-1",
        endpoint_url="http://seaweedfs:8333",
        public_endpoint_url="https://glados.example.test",
        use_ssl=False,
    )


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_s3_link_downloads_a_step_file_as_its_own_type() -> None:
    query = _query(_s3().get_url("made_items/1/step/abc.step", "Gehäuse.step"))

    assert query["response-content-type"] == "model/step"
    assert query["response-content-disposition"] == (
        "attachment; filename=\"Geh?use.step\"; filename*=UTF-8''Geh%C3%A4use.step"
    )


def test_s3_link_shows_a_pdf_inline_and_names_it_after_the_key_by_default() -> None:
    query = _query(_s3().get_url("made_items/1/pdf/abc.pdf"))

    assert query["response-content-type"] == "application/pdf"
    assert query["response-content-disposition"].startswith('inline; filename="abc.pdf"')


def test_s3_link_never_shows_svg_inline() -> None:
    query = _query(_s3().get_url("public/logo.svg"))

    assert query["response-content-type"] == "image/svg+xml"
    assert query["response-content-disposition"].startswith("attachment;")


def test_azure_link_carries_the_same_overrides() -> None:
    adapter = AzureStorageAdapter(
        container="objects",
        account_name="account",
        account_key="c2VjcmV0",
        endpoint_url=None,
    )

    query = _query(adapter.get_url("made_items/1/dxf/abc.dxf", "plate.dxf"))

    assert query["rsct"] == "application/dxf"
    assert query["rscd"].startswith('attachment; filename="plate.dxf"')


def test_s3_presigns_with_sigv4_so_seaweedfs_accepts_the_overrides() -> None:
    query = _query(_s3().get_url("items/1/step/part.step", file_name="part.step"))
    assert query["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert "Signature" not in query
    assert "response-content-disposition" in query
