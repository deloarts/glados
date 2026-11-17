"""
HTTP-level coverage for additive download routes: `GET
/{parent}/{id}/files/{file_id}` for bought/made/source items, products,
orders, and production orders. Unlike test_api_item_files.py (which runs
with storage disabled, so it only exercises routing), local storage is
enabled here via the `storage` fixture, so these are real round trips:
bytes are written directly at the local adapter's resolved path,
bypassing the multipart upload endpoints, which would need a supplier/
manufacturer/project graph per family just to satisfy FK-shaped fields
that SQLite here does not even enforce, and are then fetched back over HTTP.

Each family gets a 200 that returns the exact bytes, and a 404 for the new
cross-parent guard (a file that exists but belongs to a *different*
parent must 404, never 403, since there is no cross-parent existence oracle).
Production orders additionally get a 403 without write:inspections: this
is the one family whose download gate is not "any authenticated user",
matching its list route.

test_no_media_route_is_registered pins that no unauthenticated `/media`
StaticFiles mount exists beside the explicit authenticated download
endpoints above, so a `/media/...` path 404s like any other unknown route.
"""

import itertools
from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_file_repository import (
    SqlAlchemyBoughtItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_file_repository import (
    SqlAlchemyMadeItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_file_repository import (
    SqlAlchemySourceItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_file_repository import (
    SqlAlchemyOrderFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_file_repository import (
    SqlAlchemyProductionOrderFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.product_file_repository import (
    SqlAlchemyProductFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory

BACKUP_PATH = "backups"


@pytest.fixture
async def storage(db, tmp_path, monkeypatch):
    """Enable the local storage provider, rooted in a temp dir."""
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
            backup_enabled=True,
            backup_path=BACKUP_PATH,
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    return media


def _write_object(media_dir, key: str, data: bytes) -> None:
    path = media_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.fixture
async def any_authenticated_user(auth_client):
    """The download gate for five of the six families equals their list
    gate: any authenticated user, no specific permission."""
    return await auth_client(permissions=[])


@pytest.fixture
async def inspector(auth_client):
    return await auth_client(permissions=[Permission.WRITE_INSPECTIONS])


@pytest.fixture
async def production_writer(auth_client):
    # Holds write:production_orders but NOT write:inspections.
    return await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])


# ── Parent + file seeding helpers ───────────────────────────────────────
# FK-shaped fields (manufacturer_id, supplier_id, ...) are left pointing at
# ids that need not exist: SQLite here does not enforce foreign keys (see
# tests/integration/test_api_production_state_machine.py's docstring for
# the same pattern), so seeding a minimal parent row is enough.


async def _bought_item(db, *, id_suffix: str) -> BoughtItem:
    saved = await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            article_name=f"Widget {id_suffix}",
            order_code_1=f"OC-{id_suffix}",
            order_code_2=None,
            gtin=None,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            manufacturer_id=1,
            article_group_ids=[],
            successor_item_id=None,
        )
    )
    await db.commit()
    return saved


async def _made_item(db, *, id_suffix: str) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"Made part {id_suffix}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return seeded


async def _source_item(db, *, id_suffix: str) -> SourceItem:
    saved = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=1,
            dimension=None,
            material=f"Material {id_suffix}",
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
    return saved


async def _product(db, *, id_suffix: str) -> Product:
    saved = await SqlAlchemyProductRepository(db).save(
        Product(id=0, created=datetime.now(UTC), product_number=f"P-{id_suffix}", creator_id=1)
    )
    await db.commit()
    return saved


async def _order(db, *, id_suffix: str) -> Order:
    saved = await SqlAlchemyOrderRepository(db).save(
        Order(
            id=0,
            order_number=f"ORD-{id_suffix}",
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderStatus.DRAFT,
            note=None,
            ordered_date=None,
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=1,
            supplier_id=1,
        )
    )
    await db.commit()
    return saved


# queue_sequence carries a partial unique index
# per scope (live orders only); _production_order always builds a QUEUED
# order with machine_id=None, so two calls in one test (the "belongs to
# another order" case) need distinct values, using a module-global counter,
# the same fix as test_production_order_repository.py's _make_order.
_queue_sequence_seq = itertools.count(1)


async def _production_order(db, *, id_suffix: str) -> ProductionOrder:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number=f"P-DL-{id_suffix}")
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"Download test part {id_suffix}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=f"LN-DL-{id_suffix}",
            quantity=1.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
            source_made_item_id=made_item.id,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=1.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=lot.id,
        )
    )
    saved = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-DL-{id_suffix}",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=next(_queue_sequence_seq),
            quantity=1.0,
            quantity_completed=0.0,
            estimated_duration_minutes=10,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=1,
            machine_id=None,
            lot_position_id=position.id,
        )
    )
    await db.commit()
    return saved


# ── Tests ────────────────────────────────────────────────────────────


class TestBoughtItemFileDownload:
    async def test_downloads_the_stored_bytes(self, db, storage, any_authenticated_user):
        item = await _bought_item(db, id_suffix="dl1")
        key = f"bought_items/{item.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-bought")
        file = await SqlAlchemyBoughtItemFileRepository(db).save(
            BoughtItemFile(
                id=0,
                bought_item_id=item.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=len(b"%PDF-bought"),
                storage_path=key,
                sha256="x",
                category=BoughtItemFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/bought-items/{item.id}/files/{file.id}"
        )

        assert response.status_code == 200
        assert response.content == b"%PDF-bought"
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_a_file_belonging_to_another_item_is_not_found(
        self, db, storage, any_authenticated_user
    ):
        owner = await _bought_item(db, id_suffix="dl2a")
        other = await _bought_item(db, id_suffix="dl2b")
        key = f"bought_items/{owner.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-bought")
        file = await SqlAlchemyBoughtItemFileRepository(db).save(
            BoughtItemFile(
                id=0,
                bought_item_id=owner.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                storage_path=key,
                sha256="x",
                category=BoughtItemFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/bought-items/{other.id}/files/{file.id}"
        )

        assert response.status_code == 404


class TestMadeItemFileDownload:
    async def test_downloads_the_stored_bytes(self, db, storage, any_authenticated_user):
        item = await _made_item(db, id_suffix="dl1")
        key = f"made_items/{item.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-made")
        file = await SqlAlchemyMadeItemFileRepository(db).save(
            MadeItemFile(
                id=0,
                made_item_id=item.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=len(b"%PDF-made"),
                storage_path=key,
                sha256="x",
                category=MadeItemFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/made-items/{item.id}/files/{file.id}"
        )

        assert response.status_code == 200
        assert response.content == b"%PDF-made"

    async def test_a_file_belonging_to_another_item_is_not_found(
        self, db, storage, any_authenticated_user
    ):
        owner = await _made_item(db, id_suffix="dl2a")
        other = await _made_item(db, id_suffix="dl2b")
        key = f"made_items/{owner.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-made")
        file = await SqlAlchemyMadeItemFileRepository(db).save(
            MadeItemFile(
                id=0,
                made_item_id=owner.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                storage_path=key,
                sha256="x",
                category=MadeItemFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/made-items/{other.id}/files/{file.id}"
        )

        assert response.status_code == 404


class TestSourceItemFileDownload:
    async def test_downloads_the_stored_bytes(self, db, storage, any_authenticated_user):
        item = await _source_item(db, id_suffix="dl1")
        key = f"source_items/{item.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-source")
        file = await SqlAlchemySourceItemFileRepository(db).save(
            SourceItemFile(
                id=0,
                source_item_id=item.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=len(b"%PDF-source"),
                storage_path=key,
                sha256="x",
                category=SourceItemFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/source-items/{item.id}/files/{file.id}"
        )

        assert response.status_code == 200
        assert response.content == b"%PDF-source"

    async def test_a_file_belonging_to_another_item_is_not_found(
        self, db, storage, any_authenticated_user
    ):
        owner = await _source_item(db, id_suffix="dl2a")
        other = await _source_item(db, id_suffix="dl2b")
        key = f"source_items/{owner.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-source")
        file = await SqlAlchemySourceItemFileRepository(db).save(
            SourceItemFile(
                id=0,
                source_item_id=owner.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                storage_path=key,
                sha256="x",
                category=SourceItemFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/source-items/{other.id}/files/{file.id}"
        )

        assert response.status_code == 404


class TestProductFileDownload:
    async def test_downloads_the_stored_bytes(self, db, storage, any_authenticated_user):
        product = await _product(db, id_suffix="dl1")
        key = f"products/{product.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-product")
        file = await SqlAlchemyProductFileRepository(db).save(
            ProductFile(
                id=0,
                product_id=product.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=len(b"%PDF-product"),
                storage_path=key,
                sha256="x",
                category=ProductFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/products/{product.id}/files/{file.id}"
        )

        assert response.status_code == 200
        assert response.content == b"%PDF-product"

    async def test_a_file_belonging_to_another_product_is_not_found(
        self, db, storage, any_authenticated_user
    ):
        owner = await _product(db, id_suffix="dl2a")
        other = await _product(db, id_suffix="dl2b")
        key = f"products/{owner.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-product")
        file = await SqlAlchemyProductFileRepository(db).save(
            ProductFile(
                id=0,
                product_id=owner.id,
                file_name="spec.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                storage_path=key,
                sha256="x",
                category=ProductFileCategory.PDF,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/products/{other.id}/files/{file.id}"
        )

        assert response.status_code == 404


class TestOrderFileDownload:
    async def test_downloads_the_stored_bytes(self, db, storage, any_authenticated_user):
        order = await _order(db, id_suffix="dl1")
        key = f"orders/{order.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-order")
        file = await SqlAlchemyOrderFileRepository(db).save(
            OrderFile(
                id=0,
                order_id=order.id,
                file_name="order.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=len(b"%PDF-order"),
                storage_path=key,
                sha256="x",
                category=OrderFileCategory.GENERAL,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/orders/{order.id}/files/{file.id}"
        )

        assert response.status_code == 200
        assert response.content == b"%PDF-order"

    async def test_a_file_belonging_to_another_order_is_not_found(
        self, db, storage, any_authenticated_user
    ):
        owner = await _order(db, id_suffix="dl2a")
        other = await _order(db, id_suffix="dl2b")
        key = f"orders/{owner.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-order")
        file = await SqlAlchemyOrderFileRepository(db).save(
            OrderFile(
                id=0,
                order_id=owner.id,
                file_name="order.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                storage_path=key,
                sha256="x",
                category=OrderFileCategory.GENERAL,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await any_authenticated_user.get(
            f"/api/v1/web/orders/{other.id}/files/{file.id}"
        )

        assert response.status_code == 404


class TestProductionOrderFileDownload:
    async def test_downloads_the_stored_bytes_for_an_inspector(self, db, storage, inspector):
        order = await _production_order(db, id_suffix="dl1")
        key = f"production_orders/{order.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-po")
        file = await SqlAlchemyProductionOrderFileRepository(db).save(
            ProductionOrderFile(
                id=0,
                production_order_id=order.id,
                file_name="report.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=len(b"%PDF-po"),
                storage_path=key,
                sha256="x",
                category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await inspector.get(f"/api/v1/web/production-orders/{order.id}/files/{file.id}")

        assert response.status_code == 200
        assert response.content == b"%PDF-po"

    async def test_a_file_belonging_to_another_order_is_not_found(self, db, storage, inspector):
        owner = await _production_order(db, id_suffix="dl2a")
        other = await _production_order(db, id_suffix="dl2b")
        key = f"production_orders/{owner.id}/pdf/stored.pdf"
        _write_object(storage, key, b"%PDF-po")
        file = await SqlAlchemyProductionOrderFileRepository(db).save(
            ProductionOrderFile(
                id=0,
                production_order_id=owner.id,
                file_name="report.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                storage_path=key,
                sha256="x",
                category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        await db.commit()

        response = await inspector.get(f"/api/v1/web/production-orders/{other.id}/files/{file.id}")

        assert response.status_code == 404

    async def test_downloading_without_write_inspections_is_403(self, production_writer):
        # Permission is checked before the file lookup (matches the list
        # route's ordering), so this 403s even for ids that don't exist.
        response = await production_writer.get("/api/v1/web/production-orders/999999/files/1")
        assert response.status_code == 403


class TestNoMediaMount:
    async def test_no_media_route_is_registered(self, client):
        """The unauthenticated `/media` StaticFiles mount is gone entirely,
        not narrowed, not gated. No route answers under /media at all any
        more, authenticated or not, so this 404s even with no credentials
        (pins the randomized avatar key path too: it was never anything an
        attacker could have guessed anyway, but this proves there is no
        unauthenticated path to it regardless)."""
        response = await client.get("/media/users/avatars/1.jpg")

        assert response.status_code == 404
