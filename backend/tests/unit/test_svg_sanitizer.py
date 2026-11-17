from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from typing import cast
from xml.etree import ElementTree as ET

import pytest

from src.modules.platform.application.services.svg_sanitizer import SVG_NS
from src.modules.platform.application.services.svg_sanitizer import SvgRejectedError
from src.modules.platform.application.services.svg_sanitizer import sanitize_svg
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.workspace.application.use_cases.product._file_kind import PRODUCT_FILE_KIND
from src.modules.workspace.application.use_cases.product.upload_product_file import (
    UploadProductFile,
)
from src.modules.workspace.domain.errors import ProductFileInvalidTypeError
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from tests.unit.fakes import FakeUnitOfWork

NS = f'xmlns="{SVG_NS}" xmlns:xlink="http://www.w3.org/1999/xlink"'


def _clean(body: str, attrs: str = "") -> str:
    return sanitize_svg(f"<svg {NS} {attrs}>{body}</svg>".encode()).decode()


def _tags(svg: str) -> list[str]:
    root = ET.fromstring(svg.split("?>", 1)[1])
    return [el.tag.split("}")[1] for el in root.iter()]


def test_svg_sanitizer_keeps_a_plain_drawing() -> None:
    body = (
        '<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient>'
        '<clipPath id="c"><rect width="10" height="10"/></clipPath></defs>'
        '<g transform="translate(5,5)" clip-path="url(#c)">'
        '<path d="M0 0 L10 10" stroke="#000" stroke-width="0.5" fill="url(#g)"/>'
        '<circle cx="5" cy="5" r="2" class="hole"/>'
        '<text x="1" y="9" font-size="2">B01-W4-L</text>'
        '<use xlink:href="#c"/></g>'
        "<style>.hole { fill: none; stroke: red; }</style>"
    )
    cleaned = _clean(body, 'viewBox="0 0 100 50" width="100mm"')
    assert _tags(cleaned) == [
        "svg", "defs", "linearGradient", "stop", "clipPath", "rect",
        "g", "path", "circle", "text", "use", "style",
    ]  # fmt: skip
    assert 'viewBox="0 0 100 50"' in cleaned
    assert 'fill="url(#g)"' in cleaned
    assert 'xlink:href="#c"' in cleaned
    assert ".hole { fill: none; stroke: red; }" in cleaned
    assert "B01-W4-L" in cleaned


def test_svg_sanitizer_drops_scripts_and_foreign_objects() -> None:
    cleaned = _clean(
        "<script>alert(1)</script>"
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject>'
        '<rect width="1" height="1"/>'
    )
    assert "script" not in cleaned
    assert "alert" not in cleaned
    assert "foreignObject" not in cleaned
    assert "<rect" in cleaned


def test_svg_sanitizer_drops_event_handlers() -> None:
    cleaned = _clean('<rect width="1" height="1" onclick="alert(1)" ONLOAD="x()"/>', 'onload="a()"')
    assert "alert" not in cleaned
    assert "onload" not in cleaned.lower()


def test_svg_sanitizer_unwraps_links_and_drops_outside_hrefs() -> None:
    cleaned = _clean(
        '<a href="javascript:alert(1)"><rect width="1" height="1"/></a>'
        '<use href="https://example.com/x.svg#a"/>'
        '<image xlink:href="https://example.com/x.png" width="1" height="1"/>'
        '<image href="data:image/png;base64,iVBORw0KGgo=" width="1" height="1"/>'
    )
    assert "javascript" not in cleaned
    assert "example.com" not in cleaned
    assert "<rect" in cleaned
    assert "data:image/png;base64,iVBORw0KGgo=" in cleaned


def test_svg_sanitizer_blanks_outside_urls_in_styles() -> None:
    cleaned = _clean(
        '<style>@import url("https://example.com/a.css"); .a { fill: url(https://e.x/p) }</style>'
        '<rect style="fill: url(\'https://e.x/q\'); stroke: url(#ok)" width="1" height="1"/>'
        '<rect fill="url(https://e.x/r)" width="1" height="1"/>'
    )
    assert "example.com" not in cleaned
    assert "e.x" not in cleaned
    assert "url(#ok)" in cleaned
    assert "@import" not in cleaned


def test_svg_sanitizer_drops_unknown_namespaces_and_animation() -> None:
    cleaned = _clean(
        '<rect xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        'inkscape:label="x" width="1" height="1"/>'
        '<set attributeName="href" to="javascript:alert(1)"/>'
        '<animate attributeName="x" values="0;1"/>'
    )
    assert "inkscape" not in cleaned
    assert "javascript" not in cleaned
    assert "animate" not in cleaned


@pytest.mark.parametrize(
    "data",
    [
        b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
        b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
        b"<svg xmlns='http://www.w3.org/2000/svg'><rect></svg>",
        b"<html><body/></html>",
        b"<svg><rect/></svg>",
    ],
)
def test_svg_sanitizer_rejects_entities_malformed_and_non_svg(data: bytes) -> None:
    with pytest.raises(SvgRejectedError):
        sanitize_svg(data)


def test_svg_sanitizer_upload_accepted_only_for_the_overview() -> None:
    assert (
        PRODUCT_FILE_KIND.validate_upload(
            ProductFileCategory.DEVICE_OVERVIEW, "image/svg+xml", "top.svg", 100
        )
        == ".svg"
    )
    # Browsers on Windows send an SVG without a type; the extension counts.
    assert (
        PRODUCT_FILE_KIND.validate_upload(
            ProductFileCategory.DEVICE_OVERVIEW, "application/octet-stream", "top.SVG", 100
        )
        == ".svg"
    )
    with pytest.raises(ProductFileInvalidTypeError):
        PRODUCT_FILE_KIND.validate_upload(
            ProductFileCategory.DEVICE_RENDERING, "image/svg+xml", "cyl.svg", 100
        )


class _Storage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.uploads.append((key, data, content_type))

    async def delete(self, key: str) -> None:
        return None

    def get_url(self, key: str, file_name: str | None = None) -> str:
        return f"https://storage.test/{key}"


class _Files:
    async def get_by_item_id_and_category(self, item_id: int, category: Any) -> list[Any]:
        return []

    async def save(self, file: Any) -> Any:
        file.id = 1
        return file

    async def delete(self, file: Any) -> None:
        return None


class _Products:
    async def get_by_id(self, id: int) -> Any:
        return SimpleNamespace(id=id, designated_user_id=1, product_number="M26001", archived=False)


def _manager() -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=[Permission.MANAGE_PROJECTS],
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


async def test_svg_sanitizer_overview_upload_is_stored_cleaned_as_svg(
    fake_uow: FakeUnitOfWork,
) -> None:
    storage = _Storage()
    use_case = UploadProductFile(
        product_repo=cast(Any, _Products()),
        file_repo=cast(Any, _Files()),
        storage=cast(Any, storage),
        uow=fake_uow,
    )
    data = f'<svg {NS}><script>alert(1)</script><rect width="1" height="1"/></svg>'.encode()

    result = await use_case.execute(
        _manager(), 4, data, "top.svg", "image/svg+xml", ProductFileCategory.DEVICE_OVERVIEW
    )

    key, stored, content_type = storage.uploads[0]
    assert key.endswith(".svg")
    assert content_type == "image/svg+xml"
    assert b"script" not in stored
    assert b"<rect" in stored
    assert result.mime_type == "image/svg+xml"


async def test_svg_sanitizer_overview_upload_refuses_a_broken_svg(
    fake_uow: FakeUnitOfWork,
) -> None:
    use_case = UploadProductFile(
        product_repo=cast(Any, _Products()),
        file_repo=cast(Any, _Files()),
        storage=cast(Any, _Storage()),
        uow=fake_uow,
    )
    with pytest.raises(ProductFileInvalidTypeError):
        await use_case.execute(
            _manager(), 4, b"<svg", "top.svg", "image/svg+xml", ProductFileCategory.DEVICE_OVERVIEW
        )
