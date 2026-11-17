"""
The item picture routes, end to end against local storage in a temp dir:
a photo upload becomes the picture shown, a CAD rendering stays beside it
and can still be read by its source, the bulk listing names the picture
shown per item, and deleting the photo falls back to the next source.
Source items stand in for all three kinds, which share one router.
"""

import io
from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.item_picture_repository import (
    SqlAlchemyItemPictureRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission


def _jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 40, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
async def storage(db, tmp_path, monkeypatch):
    """Enables the local storage provider, rooted in a temp dir."""
    from src.modules.platform.infrastructure.config.settings import cfg

    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(media))

    await db.execute(text("DELETE FROM admin_storage_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_storage(
        AdminStorageSettings(
            id=1,
            provider="local",
            enabled=True,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key=None,
            region=None,
            use_ssl=False,
            backup_enabled=False,
            backup_path="backups",
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    return media


@pytest.fixture
async def writer(auth_client, storage) -> Any:
    return await auth_client(permissions=[Permission.WRITE_SOURCE_ITEMS])


async def _source_item(db: Any) -> int:
    item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=1,
            dimension=None,
            material="Pictured steel",
            mass=None,
            note=None,
            order_code_1=None,
            order_code_2=None,
            status=SourceItemCatalogueStatus.ACTIVE,
            creator_id=1,
            approver_id=None,
            manufacturer_id=None,
            successor_item_id=None,
        )
    )
    await db.commit()
    return item.id


async def _seed_cad_rendering(db: Any, storage: Any, item_id: int) -> None:
    (storage / "cad").mkdir()
    (storage / "cad" / "thumbnail.png").write_bytes(b"cad-thumbnail")
    await SqlAlchemyItemPictureRepository(db).save(
        ItemPicture(
            id=0,
            item_kind=ItemKind.SOURCE,
            item_id=item_id,
            source=ItemPictureSource.CAD_RENDERING,
            file_name="cad.png",
            image_path=None,
            image_mime_type=None,
            image_size_bytes=None,
            thumbnail_path="cad/thumbnail.png",
            thumbnail_mime_type="image/png",
            thumbnail_size_bytes=13,
            sha256="sha",
            created=datetime.now(UTC),
            uploaded_by_user_id=1,
        )
    )
    await db.commit()


async def test_a_photo_is_shown_before_the_cad_rendering_and_deleting_it_falls_back(
    db, writer, storage
) -> None:
    item_id = await _source_item(db)
    await _seed_cad_rendering(db, storage, item_id)
    base = f"{API_WEB}/source-items/{item_id}"

    uploaded = await writer.post(
        f"{base}/pictures", files={"file": ("photo.jpg", _jpeg(1600, 900), "image/jpeg")}
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["source"] == "picture"
    assert uploaded.json()["in_use"] is True

    listed = (await writer.get(f"{base}/pictures")).json()
    assert [(p["source"], p["in_use"]) for p in listed] == [
        ("picture", True),
        ("cad_rendering", False),
    ]

    shown = await writer.get(f"{base}/picture/thumbnail")
    assert shown.status_code == 200
    with Image.open(io.BytesIO(shown.content)) as thumbnail:
        assert max(thumbnail.size) == 512
    cad = await writer.get(f"{base}/pictures/cad_rendering/image")
    assert cad.content == b"cad-thumbnail"  # the image falls back to the thumbnail

    in_use = await writer.get(f"{API_WEB}/source-items-pictures/", params={"item_ids": [item_id]})
    assert [(p["item_id"], p["source"]) for p in in_use.json()] == [(item_id, "picture")]

    deleted = await writer.delete(f"{base}/pictures/picture")
    assert deleted.status_code == 204, deleted.text
    assert (await writer.get(f"{base}/picture/thumbnail")).content == b"cad-thumbnail"
    assert (await writer.delete(f"{base}/pictures/picture")).status_code == 404


async def test_an_item_without_pictures_is_a_404_and_skipped_in_bulk(db, writer) -> None:
    item_id = await _source_item(db)

    assert (await writer.get(f"{API_WEB}/source-items/{item_id}/picture/image")).status_code == 404
    in_use = await writer.get(f"{API_WEB}/source-items-pictures/", params={"item_ids": [item_id]})
    assert in_use.json() == []


async def test_a_file_that_is_no_image_is_refused(db, writer) -> None:
    item_id = await _source_item(db)

    response = await writer.post(
        f"{API_WEB}/source-items/{item_id}/pictures",
        files={"file": ("sheet.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 415, response.text


async def test_uploading_needs_the_items_write_permission(db, auth_client, storage) -> None:
    item_id = await _source_item(db)
    reader = await auth_client(permissions=[])

    response = await reader.post(
        f"{API_WEB}/source-items/{item_id}/pictures",
        files={"file": ("photo.jpg", _jpeg(10, 10), "image/jpeg")},
    )

    assert response.status_code == 403, response.text
