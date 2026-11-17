"""
Proves that the file attachment routes persist what they report. Uploading,
renaming and deleting a file, and replacing a singleton file, are each
read back through a separate request, so a use case that forgets to commit
its unit of work fails here instead of silently losing the write. Products
cover their own update and delete use cases, source items the shared bases
behind the bought, made and source item families. Local storage is enabled
in a temp dir so the uploads are real round trips.
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
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission

PDF = b"%PDF-1.7 persisted"


def _jpeg(shade: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (shade, shade, shade)).save(buffer, format="JPEG")
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
    return await auth_client(
        permissions=[
            Permission.WRITE_PROJECTS,
            Permission.MANAGE_PROJECTS,
            Permission.WRITE_SOURCE_ITEMS,
        ]
    )


async def _product_files_url(client: Any) -> str:
    response = await client.post(f"{API_WEB}/products/", json={"product_number": "P-PERSIST"})
    assert response.status_code == 201, response.text
    return f"{API_WEB}/products/{response.json()['id']}/files"


async def _source_item_files_url(db: Any) -> str:
    item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=1,
            dimension=None,
            material="Persisted steel",
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
    return f"{API_WEB}/source-items/{item.id}/files"


async def _upload(client: Any, url: str, name: str, data: bytes, mime: str, category: str) -> int:
    response = await client.post(
        url, files={"file": (name, data, mime)}, data={"category": category}
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _listed(client: Any, url: str) -> list[dict[str, Any]]:
    response = await client.get(url)
    assert response.status_code == 200, response.text
    return list(response.json())


@pytest.mark.parametrize("family", ["product", "source_item"])
async def test_upload_rename_and_delete_are_persisted(db, writer, family: str) -> None:
    url = await (_product_files_url(writer) if family == "product" else _source_item_files_url(db))

    file_id = await _upload(writer, url, "sheet.pdf", PDF, "application/pdf", "pdf")
    assert [f["id"] for f in await _listed(writer, url)] == [file_id]

    renamed = await writer.patch(f"{url}/{file_id}", json={"file_name": "renamed.pdf"})
    assert renamed.status_code == 200, renamed.text
    assert [f["file_name"] for f in await _listed(writer, url)] == ["renamed.pdf"]

    deleted = await writer.delete(f"{url}/{file_id}")
    assert deleted.status_code == 204, deleted.text
    assert await _listed(writer, url) == []


@pytest.mark.parametrize("family", ["product", "source_item"])
async def test_replacing_a_singleton_keeps_only_the_new_row_and_blob(
    db, writer, storage, family: str
) -> None:
    url = await (_product_files_url(writer) if family == "product" else _source_item_files_url(db))

    first = await _upload(writer, url, "a.pdf", PDF, "application/pdf", "pdf")
    # A source item's pictures are not files, so its singleton slot here is
    # the mesh.
    if family == "product":
        old_upload = ("old.jpg", _jpeg(10), "image/jpeg", "thumbnail")
        new_upload = ("new.jpg", _jpeg(200), "image/jpeg", "thumbnail")
    else:
        old_upload = ("old.stl", b"solid old", "model/stl", "mesh")
        new_upload = ("new.stl", b"solid new", "model/stl", "mesh")
    old_thumb = await _upload(writer, url, *old_upload)
    old_path = next(f for f in await _listed(writer, url) if f["id"] == old_thumb)["storage_path"]
    assert (storage / old_path).exists()

    new_thumb = await _upload(writer, url, *new_upload)

    files = await _listed(writer, url)
    assert sorted(f["id"] for f in files) == sorted([first, new_thumb])
    assert not (storage / old_path).exists()
