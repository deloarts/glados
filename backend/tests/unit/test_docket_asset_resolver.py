"""
Unit tests for DocketAssetResolver: the part-image and company-branding
lookups a docket needs that a ZPL label never does. Every method must
degrade to None on any gap (missing file, disabled storage, broken
download) rather than raise: a docket must still print without a photo.
"""

from dataclasses import dataclass
from typing import Any

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from tests.unit.item_picture_fakes import FakeItemPictureRepository
from tests.unit.item_picture_fakes import make_picture

# The two sizes a picture is stored in, as the keys these tests describe an
# item's picture with.
_IMAGE = "image"
_THUMBNAIL = "thumbnail"


@dataclass
class _FakeFile:
    storage_path: str


def _pictures(kind: ItemKind, files: dict[tuple[int, Any], list[_FakeFile]] | None) -> list[Any]:
    """One photo per item, holding the image and thumbnail paths given."""
    paths: dict[int, dict[str, str]] = {}
    for (item_id, variant), stored in (files or {}).items():
        if stored:
            paths.setdefault(item_id, {})[variant] = stored[0].storage_path
    return [
        make_picture(
            kind,
            item_id,
            ItemPictureSource.PICTURE,
            image_path=variants.get(_IMAGE),
            thumbnail_path=variants.get(_THUMBNAIL),
        )
        for item_id, variants in paths.items()
    ]


class _FakeAdminSettingsRepo:
    def __init__(self, company_name: str | None = None, company_logo_key: str | None = None):
        self._company_name = company_name
        self._company_logo_key = company_logo_key

    async def get_general(self) -> AdminGeneralSettings:
        return AdminGeneralSettings(
            id=1,
            company_name=self._company_name,
            company_legal_name=None,
            company_logo_key=self._company_logo_key,
            contact_email=None,
            imprint_url=None,
            privacy_url=None,
            support_url=None,
            product_number_pattern="",
            project_number_pattern="",
            allow_headless_projects=True,
            empty_value_placeholder="-",
            office_launcher_enabled=False,
            office_sharepoint_url="",
            default_language=Language.enGB,
            default_timezone="Europe/Vienna",
            default_date_format=DateFormat.ISO,
            currency="EUR",
        )


class _FakeStorage:
    def __init__(self, files: dict[str, bytes] | None = None, raise_on_download: bool = False):
        self._files = files or {}
        self._raise = raise_on_download

    async def download(self, key: str) -> tuple[bytes, str]:
        if self._raise:
            raise RuntimeError("storage is down")
        return self._files[key], "image/png"


class _Root:
    def __init__(self, id: int | None = None, made_item_id: int | None = None):
        self.id = id
        self.made_item_id = made_item_id


def _resolver(
    made_files=None, bought_files=None, source_files=None, general=None, storage=None
) -> DocketAssetResolver:
    return DocketAssetResolver(
        item_picture_repo=FakeItemPictureRepository(
            _pictures(ItemKind.MADE, made_files)
            + _pictures(ItemKind.BOUGHT, bought_files)
            + _pictures(ItemKind.SOURCE, source_files)
        ),
        admin_settings_repo=general or _FakeAdminSettingsRepo(),
        storage=storage,
    )


class TestResolvePartImage:
    async def test_made_item_docket_uses_root_id_directly(self):
        storage = _FakeStorage({"made/1/image.png": b"IMG"})
        resolver = _resolver(
            made_files={(1, _IMAGE): [_FakeFile("made/1/image.png")]},
            storage=storage,
        )
        assert await resolver.resolve_part_image("made_item", _Root(id=1)) == b"IMG"

    async def test_lot_docket_uses_made_item_id_not_root_id(self):
        storage = _FakeStorage({"made/7/image.png": b"IMG"})
        resolver = _resolver(
            made_files={(7, _IMAGE): [_FakeFile("made/7/image.png")]},
            storage=storage,
        )
        root = _Root(id=999, made_item_id=7)  # lot id != made item id
        assert await resolver.resolve_part_image("production_lot", root) == b"IMG"

    async def test_production_order_docket_uses_made_item_id(self):
        storage = _FakeStorage({"made/7/image.png": b"IMG"})
        resolver = _resolver(
            made_files={(7, _IMAGE): [_FakeFile("made/7/image.png")]},
            storage=storage,
        )
        root = _Root(id=999, made_item_id=7)
        assert await resolver.resolve_part_image("production_order", root) == b"IMG"

    async def test_bought_item_docket_uses_bought_category_and_root_id(self):
        storage = _FakeStorage({"bought/3/image.png": b"IMG"})
        resolver = _resolver(
            bought_files={(3, _IMAGE): [_FakeFile("bought/3/image.png")]},
            storage=storage,
        )
        assert await resolver.resolve_part_image("bought_item", _Root(id=3)) == b"IMG"

    async def test_source_item_docket_uses_source_category_and_root_id(self):
        storage = _FakeStorage({"source/4/image.png": b"IMG"})
        resolver = _resolver(
            source_files={(4, _IMAGE): [_FakeFile("source/4/image.png")]},
            storage=storage,
        )
        assert await resolver.resolve_part_image("source_item", _Root(id=4)) == b"IMG"

    async def test_falls_back_to_thumbnail_when_no_full_image(self):
        storage = _FakeStorage({"made/1/thumb.png": b"THUMB"})
        resolver = _resolver(
            made_files={(1, _THUMBNAIL): [_FakeFile("made/1/thumb.png")]},
            storage=storage,
        )
        assert await resolver.resolve_part_image("made_item", _Root(id=1)) == b"THUMB"

    async def test_no_file_at_all_resolves_to_none(self):
        resolver = _resolver(storage=_FakeStorage())
        assert await resolver.resolve_part_image("made_item", _Root(id=1)) is None

    async def test_storage_disabled_resolves_to_none_even_with_a_file_row(self):
        resolver = _resolver(
            made_files={(1, _IMAGE): [_FakeFile("made/1/image.png")]},
            storage=None,
        )
        assert await resolver.resolve_part_image("made_item", _Root(id=1)) is None

    async def test_broken_storage_download_resolves_to_none_not_a_raise(self):
        resolver = _resolver(
            made_files={(1, _IMAGE): [_FakeFile("made/1/image.png")]},
            storage=_FakeStorage(raise_on_download=True),
        )
        assert await resolver.resolve_part_image("made_item", _Root(id=1)) is None

    async def test_broken_storage_download_logs_a_warning_naming_the_asset(self, glados_caplog):
        resolver = _resolver(
            made_files={(1, _IMAGE): [_FakeFile("made/1/image.png")]},
            storage=_FakeStorage(raise_on_download=True),
        )

        await resolver.resolve_part_image("made_item", _Root(id=1))

        (record,) = [r for r in glados_caplog.records if r.levelname == "WARNING"]
        assert "made/1/image.png" in record.getMessage()
        assert record.exc_info is not None

    async def test_order_item_root_type_has_no_reachable_image(self):
        resolver = _resolver(storage=_FakeStorage())
        assert await resolver.resolve_part_image("order_item", _Root(id=1)) is None

    async def test_missing_id_on_root_resolves_to_none(self):
        resolver = _resolver(storage=_FakeStorage())
        assert await resolver.resolve_part_image("made_item", _Root(id=None)) is None


class TestResolveCompanyLogo:
    async def test_resolves_bytes_when_key_and_storage_are_present(self):
        storage = _FakeStorage({"branding/logo.png": b"LOGO"})
        resolver = _resolver(
            general=_FakeAdminSettingsRepo(company_logo_key="branding/logo.png"), storage=storage
        )
        assert await resolver.resolve_company_logo() == b"LOGO"

    async def test_no_key_resolves_to_none(self):
        resolver = _resolver(
            general=_FakeAdminSettingsRepo(company_logo_key=None), storage=_FakeStorage()
        )
        assert await resolver.resolve_company_logo() is None

    async def test_no_storage_resolves_to_none(self):
        resolver = _resolver(
            general=_FakeAdminSettingsRepo(company_logo_key="branding/logo.png"), storage=None
        )
        assert await resolver.resolve_company_logo() is None


class TestResolveCompanyName:
    async def test_returns_configured_name(self):
        resolver = _resolver(general=_FakeAdminSettingsRepo(company_name="Example Ltd"))
        assert await resolver.resolve_company_name() == "Example Ltd"

    async def test_none_name_resolves_to_empty_string(self):
        resolver = _resolver(general=_FakeAdminSettingsRepo(company_name=None))
        assert await resolver.resolve_company_name() == ""


class _Row:
    """An order line as the row-image lookup sees it: exactly one of the
    three catalogue ids set, or none at all for a VIRTUAL line."""

    def __init__(self, bought_item_id=None, source_item_id=None, made_item_id=None):
        self.bought_item_id = bought_item_id
        self.source_item_id = source_item_id
        self.made_item_id = made_item_id


class TestResolveRowImage:
    async def test_bought_line_resolves_through_the_bought_item_files(self):
        resolver = _resolver(
            bought_files={(7, _IMAGE): [_FakeFile("b/7.png")]},
            storage=_FakeStorage({"b/7.png": b"BOUGHT"}),
        )
        assert await resolver.resolve_row_image(_Row(bought_item_id=7)) == b"BOUGHT"

    async def test_source_line_resolves_through_the_source_item_files(self):
        resolver = _resolver(
            source_files={(3, _IMAGE): [_FakeFile("s/3.png")]},
            storage=_FakeStorage({"s/3.png": b"SOURCE"}),
        )
        assert await resolver.resolve_row_image(_Row(source_item_id=3)) == b"SOURCE"

    async def test_made_line_resolves_through_the_made_item_files(self):
        resolver = _resolver(
            made_files={(9, _IMAGE): [_FakeFile("m/9.png")]},
            storage=_FakeStorage({"m/9.png": b"MADE"}),
        )
        assert await resolver.resolve_row_image(_Row(made_item_id=9)) == b"MADE"

    async def test_thumbnail_is_used_when_there_is_no_full_image(self):
        resolver = _resolver(
            bought_files={(7, _THUMBNAIL): [_FakeFile("b/7t.png")]},
            storage=_FakeStorage({"b/7t.png": b"THUMB"}),
        )
        assert await resolver.resolve_row_image(_Row(bought_item_id=7)) == b"THUMB"

    async def test_virtual_line_has_nothing_to_show(self):
        assert await _resolver(storage=_FakeStorage()).resolve_row_image(_Row()) is None

    async def test_line_whose_item_has_no_file_resolves_to_none(self):
        resolver = _resolver(storage=_FakeStorage())
        assert await resolver.resolve_row_image(_Row(bought_item_id=7)) is None

    async def test_broken_download_resolves_to_none_rather_than_raising(self):
        resolver = _resolver(
            bought_files={(7, _IMAGE): [_FakeFile("b/7.png")]},
            storage=_FakeStorage(raise_on_download=True),
        )
        assert await resolver.resolve_row_image(_Row(bought_item_id=7)) is None

    async def test_the_same_article_on_several_lines_is_downloaded_once(self):
        class _CountingStorage(_FakeStorage):
            def __init__(self, files):
                super().__init__(files)
                self.calls = 0

            async def download(self, key):
                self.calls += 1
                return await super().download(key)

        storage = _CountingStorage({"b/7.png": b"BOUGHT"})
        resolver = _resolver(
            bought_files={(7, _IMAGE): [_FakeFile("b/7.png")]},
            storage=storage,
        )
        for _ in range(4):
            assert await resolver.resolve_row_image(_Row(bought_item_id=7)) == b"BOUGHT"
        assert storage.calls == 1
