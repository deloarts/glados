"""
Unit tests for the six Download<X>File use cases. File download routes
added to support: `GET /{parent}/{id}/files/{file_id}` for bought/made/source
items, products, orders, and production orders.

Parametrized across all six families: each gets the same five cases,
successful download; the cross-parent 404 guard (a file that exists but
belongs to a *different* parent must 404, never 403, since there is no
cross-parent existence oracle); an unknown file id; storage-disabled; and the
read transaction ending before the storage download. The
production-order family additionally needs write:inspections; its
permission-specific tests live in test_item_file_permissions.py beside its
sibling list/upload/update/delete gate tests.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from typing import NamedTuple

import pytest

from src.modules.catalogue.application.use_cases.bought_item.download_bought_item_file import (
    DownloadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.item_picture._kinds import BOUGHT_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture._kinds import MADE_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture._kinds import SOURCE_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture.download_item_picture import (
    DownloadItemPicture,
)
from src.modules.catalogue.application.use_cases.made_item.download_made_item_file import (
    DownloadMadeItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.download_source_item_file import (
    DownloadSourceItemFile,
)
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.errors import BoughtItemFileNotFoundError
from src.modules.catalogue.domain.errors import MadeItemFileNotFoundError
from src.modules.catalogue.domain.errors import SourceItemFileNotFoundError
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.fulfillment.application.use_cases.order.download_order_file import (
    DownloadOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.download_production_order_file import (
    DownloadProductionOrderFile,
)
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.errors import OrderFileNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderFileNotFoundError
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.application.use_cases.admin_settings.get_login_background_video import (
    GetLoginBackgroundVideo,
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
from src.modules.workspace.application.use_cases.product.download_product_file import (
    DownloadProductFile,
)
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.errors import ProductFileNotFoundError
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory


def make_actor(permissions: list[str] | None = None) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=permissions if permissions is not None else [],
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


class FakeFileRepo:
    def __init__(self, files: list[Any] | None = None) -> None:
        self._files = {f.id: f for f in (files or [])}

    async def get_by_id(self, id: int) -> Any:
        return self._files.get(id)


class FakeStorage:
    def __init__(
        self, objects: dict[str, tuple[bytes, str]] | None = None, log: list[str] | None = None
    ) -> None:
        self._objects = objects or {}
        self._log = log if log is not None else []

    async def download(self, key: str) -> tuple[bytes, str]:
        self._log.append(f"download:{key}")
        return self._objects[key]


class RecordingUow:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


class Family(NamedTuple):
    name: str
    use_case: type
    entity: type
    not_found: type[Exception]
    parent_field: str
    make_entity: Any  # (file_id, parent_id) -> entity
    call: Any  # (use_case, parent_id, file_id) -> (entity, bytes, content_type)


def _bought_entity(file_id: int, parent_id: int) -> BoughtItemFile:
    return BoughtItemFile(
        id=file_id,
        bought_item_id=parent_id,
        file_name="spec.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"bought_items/{parent_id}/pdf/stored.pdf",
        sha256="x",
        category=BoughtItemFileCategory.PDF,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


def _made_entity(file_id: int, parent_id: int) -> MadeItemFile:
    return MadeItemFile(
        id=file_id,
        made_item_id=parent_id,
        file_name="spec.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"made_items/{parent_id}/pdf/stored.pdf",
        sha256="x",
        category=MadeItemFileCategory.PDF,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


def _source_entity(file_id: int, parent_id: int) -> SourceItemFile:
    return SourceItemFile(
        id=file_id,
        source_item_id=parent_id,
        file_name="spec.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"source_items/{parent_id}/pdf/stored.pdf",
        sha256="x",
        category=SourceItemFileCategory.PDF,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


def _product_entity(file_id: int, parent_id: int) -> ProductFile:
    return ProductFile(
        id=file_id,
        product_id=parent_id,
        file_name="spec.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"products/{parent_id}/pdf/stored.pdf",
        sha256="x",
        category=ProductFileCategory.PDF,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


def _order_entity(file_id: int, parent_id: int) -> OrderFile:
    return OrderFile(
        id=file_id,
        order_id=parent_id,
        file_name="order.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"orders/{parent_id}/pdf/stored.pdf",
        sha256="x",
        category=OrderFileCategory.GENERAL,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


def _production_order_entity(file_id: int, parent_id: int) -> ProductionOrderFile:
    return ProductionOrderFile(
        id=file_id,
        production_order_id=parent_id,
        file_name="report.pdf",
        stored_name="stored.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"production_orders/{parent_id}/pdf/stored.pdf",
        sha256="x",
        category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


_INSPECTOR = make_actor([Permission.WRITE_INSPECTIONS])

FAMILIES: list[Family] = [
    Family(
        "bought_item",
        DownloadBoughtItemFile,
        BoughtItemFile,
        BoughtItemFileNotFoundError,
        "bought_item_id",
        _bought_entity,
        lambda uc, parent_id, file_id: uc.execute(item_id=parent_id, file_id=file_id),
    ),
    Family(
        "made_item",
        DownloadMadeItemFile,
        MadeItemFile,
        MadeItemFileNotFoundError,
        "made_item_id",
        _made_entity,
        lambda uc, parent_id, file_id: uc.execute(item_id=parent_id, file_id=file_id),
    ),
    Family(
        "source_item",
        DownloadSourceItemFile,
        SourceItemFile,
        SourceItemFileNotFoundError,
        "source_item_id",
        _source_entity,
        lambda uc, parent_id, file_id: uc.execute(item_id=parent_id, file_id=file_id),
    ),
    Family(
        "product",
        DownloadProductFile,
        ProductFile,
        ProductFileNotFoundError,
        "product_id",
        _product_entity,
        lambda uc, parent_id, file_id: uc.execute(product_id=parent_id, file_id=file_id),
    ),
    Family(
        "order",
        DownloadOrderFile,
        OrderFile,
        OrderFileNotFoundError,
        "order_id",
        _order_entity,
        lambda uc, parent_id, file_id: uc.execute(order_id=parent_id, file_id=file_id),
    ),
    Family(
        "production_order",
        DownloadProductionOrderFile,
        ProductionOrderFile,
        ProductionOrderFileNotFoundError,
        "production_order_id",
        _production_order_entity,
        lambda uc, parent_id, file_id: uc.execute(
            actor=_INSPECTOR, order_id=parent_id, file_id=file_id
        ),
    ),
]


@pytest.mark.parametrize("family", FAMILIES, ids=[f.name for f in FAMILIES])
class TestFileDownloadUseCases:
    async def test_download_returns_the_stored_bytes_and_mime_type(self, family: Family) -> None:
        entity = family.make_entity(1, 42)
        storage = FakeStorage({entity.storage_path: (b"file-bytes", "application/pdf")})
        uc = family.use_case(file_repo=FakeFileRepo([entity]), storage=storage)

        result_file, data, content_type = await family.call(uc, 42, 1)

        assert data == b"file-bytes"
        assert content_type == "application/pdf"
        assert result_file.id == 1

    async def test_read_transaction_ends_before_the_storage_download(self, family: Family) -> None:
        log: list[str] = []
        entity = family.make_entity(1, 42)
        storage = FakeStorage({entity.storage_path: (b"file-bytes", "application/pdf")}, log)
        uc = family.use_case(
            file_repo=FakeFileRepo([entity]), storage=storage, uow=RecordingUow(log)
        )

        await family.call(uc, 42, 1)

        assert log == ["commit", f"download:{entity.storage_path}"]

    async def test_file_belonging_to_another_parent_is_not_found(self, family: Family) -> None:
        entity = family.make_entity(1, 2)  # belongs to parent #2
        storage = FakeStorage({entity.storage_path: (b"file-bytes", "application/pdf")})
        uc = family.use_case(file_repo=FakeFileRepo([entity]), storage=storage)

        with pytest.raises(family.not_found):
            await family.call(uc, 1, 1)  # requested via parent #1

    async def test_unknown_file_id_is_not_found(self, family: Family) -> None:
        uc = family.use_case(file_repo=FakeFileRepo([]), storage=FakeStorage({}))

        with pytest.raises(family.not_found):
            await family.call(uc, 1, 999)

    async def test_download_when_storage_is_disabled_raises_storage_not_enabled(
        self, family: Family
    ) -> None:
        entity = family.make_entity(1, 42)
        uc = family.use_case(file_repo=FakeFileRepo([entity]), storage=None)

        with pytest.raises(StorageNotEnabledError):
            await family.call(uc, 42, 1)


# ── Thumbnail and login video downloads ──────────────────────────────


class FakeBrandingRepo:
    def __init__(self, key: str) -> None:
        self._key = key

    async def get_branding(self) -> Any:
        return SimpleNamespace(login_background_video_key=self._key)


class FakePictureRepo:
    def __init__(self, pictures: list[ItemPicture]) -> None:
        self._pictures = pictures

    async def get_by_item(self, kind: ItemKind, item_id: int) -> list[ItemPicture]:
        return [p for p in self._pictures if p.item_kind is kind and p.item_id == item_id]


@pytest.mark.parametrize(
    "kind",
    [MADE_ITEM_PICTURES, BOUGHT_ITEM_PICTURES, SOURCE_ITEM_PICTURES],
    ids=["made", "bought", "source"],
)
async def test_picture_read_transaction_ends_before_the_storage_download(kind: Any) -> None:
    log: list[str] = []
    storage = FakeStorage({"pictures/1-thumbnail.png": (b"png", "image/png")}, log)
    picture = ItemPicture(
        id=1,
        item_kind=kind.kind,
        item_id=1,
        source=ItemPictureSource.PICTURE,
        file_name="photo.jpg",
        image_path="pictures/1.png",
        image_mime_type="image/png",
        image_size_bytes=3,
        thumbnail_path="pictures/1-thumbnail.png",
        thumbnail_mime_type="image/png",
        thumbnail_size_bytes=3,
        sha256="x",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        uploaded_by_user_id=1,
    )
    uc = DownloadItemPicture(kind, FakePictureRepo([picture]), storage, RecordingUow(log))  # type: ignore[arg-type]

    assert await uc.execute(1, ItemPictureVariant.THUMBNAIL) == (b"png", "image/png")
    assert log == ["commit", "download:pictures/1-thumbnail.png"]


async def test_login_video_read_transaction_ends_before_the_storage_download() -> None:
    log: list[str] = []
    storage = FakeStorage({"public/login-background.mp4": (b"mp4", "video/mp4")}, log)
    uc = GetLoginBackgroundVideo(
        repo=FakeBrandingRepo("public/login-background.mp4"),
        storage=storage,
        uow=RecordingUow(log),
    )

    assert await uc.execute() == (b"mp4", "video/mp4")
    assert log == ["commit", "download:public/login-background.mp4"]
