"""The infoscreen feed with real rows: overdue lots in the lots due widget,
orders waiting on a pool in the machine board, and the thumbnail links the
rows carry, served without a credential and refused once expired, forged or
archived."""

import io
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
from src.modules.operations.infrastructure.security.terminal_auth import read_thumbnail_token
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._tenant_day import tenant_today
from tests.integration._terminal_helpers import INFOSCREENS
from tests.integration._terminal_helpers import device_client
from tests.integration._terminal_helpers import seed_production
from tests.integration._terminal_helpers import seed_security

pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")


@pytest.fixture(autouse=True)
async def _settings(db: AsyncSession) -> None:
    await seed_security(db)
    await seed_production(db)


@pytest.fixture
async def storage(db: AsyncSession, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Local storage rooted in a temp dir, as the item picture tests use."""
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
async def writer(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[Permission.WRITE_INFOSCREENS, Permission.WRITE_MACHINES],
        username="writer",
        email="writer@example.com",
    )


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _picture(db: AsyncSession, storage: Any, kind: ItemKind, item_id: int) -> bytes:
    data = _png()
    folder = storage / f"{kind.value}-{item_id}"
    folder.mkdir()
    (folder / "thumbnail.png").write_bytes(data)
    await SqlAlchemyItemPictureRepository(db).save(
        ItemPicture(
            id=0,
            item_kind=kind,
            item_id=item_id,
            source=ItemPictureSource.PICTURE,
            file_name="photo.png",
            image_path=None,
            image_mime_type=None,
            image_size_bytes=None,
            thumbnail_path=f"{kind.value}-{item_id}/thumbnail.png",
            thumbnail_mime_type="image/png",
            thumbnail_size_bytes=len(data),
            sha256="sha",
            created=datetime.now(UTC),
            uploaded_by_user_id=1,
        )
    )
    await db.commit()
    return data


async def _source_item(db: AsyncSession) -> SourceItem:
    item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=1,
            dimension=None,
            material="Round bar",
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
    return item


async def _screen(writer: httpx.AsyncClient, pages: list[dict[str, Any]]) -> int:
    response = await writer.post(INFOSCREENS, json={"name": "Rows", "pages": pages})
    assert response.status_code == 201, response.text
    screen_id: int = response.json()["id"]
    return screen_id


async def test_infoscreen_overdue_lot_and_pool_queue_show_with_thumbnails(
    db: AsyncSession, storage: Any, writer: httpx.AsyncClient
) -> None:
    pool = await writer.post("/api/v1/web/production-machine-pools/", json={"name": "CNC milling"})
    assert pool.status_code == 201, pool.text
    pool_id = pool.json()["id"]
    await _picture(db, storage, ItemKind.MADE, 1)

    # The feed counts days in the tenant's timezone.
    today = tenant_today()
    overdue = await seed.lot(db, "planned", required_delivery_date=today - timedelta(days=8))
    later = await seed.lot(db, "planned", required_delivery_date=today + timedelta(days=3))
    beyond = await seed.lot(db, "planned", required_delivery_date=today + timedelta(days=30))
    for lot, sequence in ((overdue, 1), (later, 2), (beyond, 3)):
        position = await seed.position(db, lot, "internal", "ordered_or_queued")
        await seed.production_order(
            db,
            position,
            "queued",
            machine_id=None,
            machine_pool_id=pool_id,
            queue_sequence=sequence,
        )
    await db.commit()

    screen_id = await _screen(
        writer,
        [
            {
                "layout": "two_columns",
                "slots": [
                    {"type": "lots_due", "horizon_days": 7, "pool_ids": [pool_id]},
                    {"type": "machine_board", "pool_ids": [pool_id], "next_count": 2},
                ],
            }
        ],
    )
    feed = (await writer.get(f"{INFOSCREENS}/{screen_id}/feed")).json()
    lots, board = feed["widgets"][0]

    assert [(r["lot_number"], r["days_late"]) for r in lots["lots"]] == [
        (overdue.lot_number, 8),
        (later.lot_number, None),
    ]
    assert all(r["thumbnail_url"] for r in lots["lots"])

    assert board["machines"] == []
    [queue] = board["pools"]
    assert queue["pool_id"] == pool_id
    assert queue["pool_name"] == "CNC milling"
    assert queue["waiting_total"] == 3
    assert [c["lot_number"] for c in queue["waiting"]] == [overdue.lot_number, later.lot_number]
    assert queue["waiting"][0]["thumbnail_url"] == lots["lots"][0]["thumbnail_url"]

    again = (await writer.get(f"{INFOSCREENS}/{screen_id}/feed")).json()
    assert again["widgets"][0][0]["lots"][0]["thumbnail_url"] == lots["lots"][0]["thumbnail_url"]


async def test_infoscreen_machine_board_lists_no_pools_when_only_machines_are_chosen(
    writer: httpx.AsyncClient,
) -> None:
    await writer.post("/api/v1/web/production-machine-pools/", json={"name": "Pool"})
    machine = await writer.post(
        "/api/v1/web/production-machines/",
        json={"internal_name": "Mill", "vendor": "DMG", "model": "DMU"},
    )
    only_machines = await _screen(
        writer,
        [
            {
                "layout": "full",
                "slots": [{"type": "machine_board", "machine_ids": [machine.json()["id"]]}],
            }
        ],
    )
    board = (await writer.get(f"{INFOSCREENS}/{only_machines}/feed")).json()["widgets"][0][0]
    assert [m["machine_name"] for m in board["machines"]] == ["Mill"]
    assert board["pools"] == []

    everything = await writer.patch(
        f"{INFOSCREENS}/{only_machines}",
        json={"pages": [{"layout": "full", "slots": [{"type": "machine_board"}]}]},
    )
    assert everything.status_code == 200
    board = (await writer.get(f"{INFOSCREENS}/{only_machines}/feed")).json()["widgets"][0][0]
    assert [p["pool_name"] for p in board["pools"]] == ["Pool"]
    assert board["pools"][0]["waiting"] == []


async def test_infoscreen_thumbnail_link_serves_the_image_until_archived(
    db: AsyncSession, storage: Any, writer: httpx.AsyncClient
) -> None:
    source = await _source_item(db)
    image = await _picture(db, storage, ItemKind.SOURCE, source.id)
    # Expected on the tenant's today, the first day the widget lists.
    order = await seed.order(db, "ordered", expected_delivery_date=tenant_today())
    line = await seed.line(db, order, "ordered", expected_delivery_date=tenant_today())
    line.line_type = "SOURCE"
    line.bought_item_id = None
    line.source_item_id = source.id
    await db.commit()

    screen_id = await _screen(
        writer, [{"layout": "full", "slots": [{"type": "deliveries_expected"}]}]
    )
    feed = (await writer.get(f"{INFOSCREENS}/{screen_id}/feed")).json()
    [row] = feed["widgets"][0][0]["deliveries"]
    url = row["thumbnail_url"]
    assert url.startswith("/api/v1/web/terminal-device/thumbnails/")
    claims = read_thumbnail_token(url.rsplit("/", 1)[1], datetime.now(UTC))
    assert claims is not None and claims[:3] == ("source", source.id, "thumbnail")

    async with device_client() as anonymous:
        served = await anonymous.get(url)
        assert served.status_code == 200, served.text
        assert served.content == image
        assert served.headers["content-type"] == "image/png"
        cache = served.headers["cache-control"]
        assert cache.startswith("private, max-age=")
        assert 0 < int(cache.split("=")[1]) <= 90 * 60

        assert (await anonymous.get(url + "x")).status_code == 404
        assert (await anonymous.get(url.replace("source", "made", 1))).status_code == 404

        source.archived = True
        await SqlAlchemySourceItemRepository(db).save(source)
        await db.commit()
        archived = await anonymous.get(url)
        assert archived.status_code == 404
        assert archived.json()["code"] == "InfoscreenThumbnailNotFoundError"
