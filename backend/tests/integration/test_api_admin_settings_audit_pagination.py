"""
GET /admin/settings/audit: skip/limit carry `Query(...)` validation and
the `MAX_PAGE_SIZE` ceiling like every other list endpoint (see logs.py's
canonical pattern). An out-of-range or negative value is rejected with
422 rather than clamped silently by the repository, matching the
OpenAPI-visible constraint the other endpoints advertise.
"""

from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/audit"


class TestPaginationValidation:
    async def test_limit_above_max_page_size_is_422(self, auth_client):
        reader = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await reader.get(BASE, params={"limit": MAX_PAGE_SIZE + 1})

        assert response.status_code == 422

    async def test_limit_zero_is_422(self, auth_client):
        reader = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await reader.get(BASE, params={"limit": 0})

        assert response.status_code == 422

    async def test_negative_skip_is_422(self, auth_client):
        reader = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await reader.get(BASE, params={"skip": -1})

        assert response.status_code == 422

    async def test_omitted_params_still_return_a_normal_page(self, auth_client):
        reader = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await reader.get(BASE)

        assert response.status_code == 200
        body = response.json()
        assert body["skip"] == 0
        assert body["items"] == []


class TestOpenApiAdvertisesTheCeiling:
    async def test_limit_carries_the_max_page_size_ceiling_in_the_openapi_schema(self, auth_client):
        schema = (await (await auth_client()).get("/api/v1/web/openapi.json")).json()
        limit_param = next(
            p for p in schema["paths"][BASE]["get"]["parameters"] if p["name"] == "limit"
        )

        assert limit_param["schema"]["anyOf"][0]["maximum"] == MAX_PAGE_SIZE
