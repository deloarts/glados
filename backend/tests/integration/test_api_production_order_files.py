"""
The QA/inspection evidence file endpoints over HTTP
(/production-orders/{id}/files). Storage is disabled in the test
environment, so these do not exercise upload round-trips. What they
cover is routing (the nested /{id}/files router must not collide with
or shadow the parent /production-orders/{id} detail route, same
collision class as test_api_item_files.py) and the write:inspections
permission gate, which, unlike every other file vertical, applies to
every route including GET, not just the mutating ones.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission


@pytest.fixture
async def inspector(auth_client):
    return await auth_client(permissions=[Permission.WRITE_INSPECTIONS])


@pytest.fixture
async def production_writer(auth_client):
    # Holds write:production_orders but NOT write:inspections, proving the
    # two are independent gates.
    return await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])


class TestProductionOrderFileRoutes:
    async def test_listing_files_of_an_unknown_order_is_404_for_an_inspector(self, inspector):
        response = await inspector.get("/api/v1/web/production-orders/999999/files")
        assert response.status_code == 404

    async def test_listing_files_without_write_inspections_is_403(self, production_writer):
        response = await production_writer.get("/api/v1/web/production-orders/999999/files")
        assert response.status_code == 403

    async def test_listing_files_without_any_auth_is_401(self, client):
        response = await client.get("/api/v1/web/production-orders/999999/files")
        assert response.status_code == 401

    async def test_uploading_without_write_inspections_is_403(self, production_writer):
        response = await production_writer.post(
            "/api/v1/web/production-orders/999999/files",
            files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
            data={"category": "measurement_report"},
        )
        assert response.status_code == 403

    async def test_deleting_without_write_inspections_is_403(self, production_writer):
        response = await production_writer.delete("/api/v1/web/production-orders/999999/files/1")
        assert response.status_code == 403

    async def test_renaming_without_write_inspections_is_403(self, production_writer):
        response = await production_writer.patch(
            "/api/v1/web/production-orders/999999/files/1", json={"file_name": "renamed.pdf"}
        )
        assert response.status_code == 403

    async def test_the_production_order_detail_route_still_resolves(self, production_writer):
        # Guards the other direction of the collision: adding a nested
        # files router under the same prefix must not shadow
        # GET /production-orders/{id}. An unknown id still 404s, but as
        # the ordinary ProductionOrderNotFoundError, not a routing 422.
        response = await production_writer.get("/api/v1/web/production-orders/999999")
        assert response.status_code == 404
