"""
The file endpoints over HTTP. Storage is disabled in the test environment, so
these do not exercise upload round-trips: what they do cover is the routing,
which nothing else does: each entity registers a nested
/{id}/files router alongside its own router plus a separate bulk router under
its own -files prefix, precisely because a flat /files path would otherwise be
swallowed by the parent's int path parameter and 422.

That collision is silent until someone calls the route, so these tests call
it for every entity.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_file_model import (
    MadeItemFileOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.external_data.adapters.outbound.persistence.models.pdm_document_link_model import (
    PdmDocumentLinkOrmModel,
)
from src.modules.platform.domain.value_objects.permission import Permission


@pytest.fixture
async def project_writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS])


@pytest.fixture
async def source_writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SOURCE_ITEMS])


async def _product(client, number="P-100"):
    response = await client.post("/api/v1/web/products/", json={"product_number": number})
    assert response.status_code == 201, response.text
    return response.json()


class TestBulkFileRoutes:
    """The bulk routes must resolve rather than being captured by the parent
    router's /{id} path parameter."""

    async def test_source_items_bulk_route_resolves(self, source_writer):
        response = await source_writer.get("/api/v1/web/source-items-files/?item_ids=1&item_ids=2")

        assert response.status_code == 200
        assert response.json() == []

    async def test_products_bulk_route_resolves(self, project_writer):
        response = await project_writer.get("/api/v1/web/products-files/?item_ids=1&item_ids=2")

        assert response.status_code == 200
        assert response.json() == []

    async def test_bought_items_bulk_route_resolves(self, project_writer):
        response = await project_writer.get("/api/v1/web/bought-items-files/?item_ids=1&item_ids=2")

        assert response.status_code == 200
        assert response.json() == []

    async def test_bulk_route_requires_at_least_one_id(self, project_writer):
        assert (await project_writer.get("/api/v1/web/products-files/")).status_code == 422


class TestPerItemFileRoutes:
    async def test_listing_files_of_a_product_with_none_is_empty(self, project_writer):
        product = await _product(project_writer)

        response = await project_writer.get(f"/api/v1/web/products/{product['id']}/files")

        assert response.status_code == 200
        assert response.json() == []

    async def test_listing_files_of_an_unknown_product_is_404(self, project_writer):
        assert (await project_writer.get("/api/v1/web/products/999999/files")).status_code == 404

    async def test_listing_files_of_an_unknown_source_item_is_404(self, source_writer):
        assert (await source_writer.get("/api/v1/web/source-items/999999/files")).status_code == 404

    async def test_the_product_detail_route_still_resolves(self, project_writer):
        # Guards the other direction of the collision: adding a nested files
        # router under the same prefix must not shadow GET /products/{id}.
        product = await _product(project_writer)

        response = await project_writer.get(f"/api/v1/web/products/{product['id']}")

        assert response.status_code == 200
        assert response.json()["product_number"] == "P-100"


@pytest.fixture
async def made_item_writer(auth_client, db):
    """Seeds the made-item numbering domain (CreateMadeItem reads it) the
    same way test_api_made_items.py's own autouse fixture does, scoped to
    just this class since no other test in this file creates a made item."""
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    return await auth_client(permissions=[Permission.WRITE_MADE_ITEMS])


class TestFromPdmFlag:
    """GetMadeItemFiles resolves `from_pdm` from IPdmDocumentLinkRepository,
    one query per listing (see ItemFileKind.to_result's docstring). Files
    are seeded directly through the ORM since storage is disabled in this
    environment and PdmDocumentSync is the only writer of a real link row."""

    async def test_a_file_backed_by_a_pdm_document_link_reports_from_pdm_true(
        self, made_item_writer, db
    ) -> None:
        resp = await made_item_writer.post(
            "/api/v1/web/made-items/", json={"revision": "A", "article_name": "Bracket"}
        )
        assert resp.status_code == 201, resp.text
        item_id = resp.json()["id"]

        linked_file = MadeItemFileOrmModel(
            made_item_id=item_id,
            file_name="drawing.pdf",
            stored_name="drawing-1.pdf",
            mime_type="application/pdf",
            size_bytes=10,
            storage_path=f"made_items/catalogue/{item_id}/drawing/drawing-1.pdf",
            sha256="a" * 64,
            category="drawing",
            created=datetime.now(UTC),
            uploaded_by_user_id=1,
        )
        unlinked_file = MadeItemFileOrmModel(
            made_item_id=item_id,
            file_name="notes.pdf",
            stored_name="notes-1.pdf",
            mime_type="application/pdf",
            size_bytes=5,
            storage_path=f"made_items/catalogue/{item_id}/pdf/notes-1.pdf",
            sha256="b" * 64,
            category="pdf",
            created=datetime.now(UTC),
            uploaded_by_user_id=1,
        )
        db.add(linked_file)
        db.add(unlinked_file)
        await db.flush()
        db.add(
            PdmDocumentLinkOrmModel(
                kind="made",
                item_id=item_id,
                item_file_id=linked_file.id,
                vault_id="V1",
                file_id=100,
                version=1,
            )
        )
        await db.commit()

        body = (await made_item_writer.get(f"/api/v1/web/made-items/{item_id}/files")).json()

        by_name = {row["file_name"]: row for row in body}
        assert by_name["drawing.pdf"]["from_pdm"] is True
        assert by_name["notes.pdf"]["from_pdm"] is False
