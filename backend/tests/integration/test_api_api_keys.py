"""
HTTP-level coverage of /api/v1/web/admin/api-keys: admin management
of API keys, gated by manage:api_keys throughout, including reads (see
the router's module docstring). CreateApiKey mints a dedicated backing
service-account User per key in the same transaction, and the raw key
value is only ever present in the create response.

The pagination/sort/search block below guards that the list route
follows the `ApiKeyFilterParams`-shaped convention every other paginated
resource follows, so an *omitted* `limit` falls through to
`DEFAULT_PAGE_SIZE` (100) rather than capping the page at a hardcoded 50,
and `search`/`order_by`/`order_dir` are honoured.
"""

from datetime import UTC
from datetime import datetime

from fastapi.testclient import TestClient

from src.modules.platform.adapters.outbound.persistence.models.api_key_model import ApiKeyOrmModel
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.const import DEFAULT_PAGE_SIZE


async def _create(client: TestClient, **overrides: object) -> dict:
    body = {"name": "CI Key"} | overrides
    resp = await client.post("/api/v1/web/admin/api-keys/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_api_key_requires_manage_permission(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.post("/api/v1/web/admin/api-keys/", json={"name": "CI Key"})
    assert resp.status_code == 403


async def test_create_api_key_rejects_missing_name(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    resp = await client.post("/api/v1/web/admin/api-keys/", json={})
    assert resp.status_code == 422


async def test_create_and_read_api_key(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    created = await _create(client)
    # The raw key value is only present on the create response.
    assert "key" in created
    assert created["name"] == "CI Key"

    resp = await client.get(f"/api/v1/web/admin/api-keys/{created['id']}")
    assert resp.status_code == 200
    read_back = resp.json()
    assert read_back["name"] == "CI Key"
    assert "key" not in read_back


async def test_read_missing_api_key_404(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    resp = await client.get("/api/v1/web/admin/api-keys/999999")
    assert resp.status_code == 404


class TestTokenLifetimeCap:
    """Settings polish batch: expires_in_days beyond the configured
    security.token_max_lifetime_days is rejected with a 422, the boundary
    itself (= cap) still succeeds. conftest's autouse `_seed_admin_settings`
    does not seed `security`, so these tests seed it themselves."""

    async def _seed_cap(self, db, token_max_lifetime_days: int) -> None:
        from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
            SqlAlchemyAdminSettingsRepository,
        )
        from src.modules.platform.domain.entities.admin_settings.security import (
            AdminSecuritySettings,
        )

        await SqlAlchemyAdminSettingsRepository(db).save_security(
            AdminSecuritySettings(
                id=1,
                enforce_totp=False,
                allow_rfid_login=True,
                allow_local_login=True,
                enable_api_key_auth=False,
                min_password_length=8,
                session_timeout_minutes=1440,
                totp_trusted_device_days=30,
                max_login_attempts=5,
                lockout_duration_minutes=15,
                token_max_lifetime_days=token_max_lifetime_days,
            )
        )
        await db.commit()

    async def test_expires_in_days_above_the_cap_is_rejected(self, auth_client, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=30)
        client: TestClient = await auth_client(permissions=["manage:api_keys"])

        resp = await client.post(
            "/api/v1/web/admin/api-keys/", json={"name": "CI Key", "expires_in_days": 31}
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "TokenLifetimeExceededError"

    async def test_expires_in_days_at_the_cap_boundary_succeeds(self, auth_client, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=30)
        client: TestClient = await auth_client(permissions=["manage:api_keys"])

        resp = await client.post(
            "/api/v1/web/admin/api-keys/", json={"name": "CI Key", "expires_in_days": 30}
        )

        assert resp.status_code == 201, resp.text

    async def test_no_expiry_is_refused_while_a_cap_is_set(self, auth_client, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=1)
        client: TestClient = await auth_client(permissions=["manage:api_keys"])

        resp = await client.post("/api/v1/web/admin/api-keys/", json={"name": "CI Key"})

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "TokenExpiryRequiredError"

    async def test_no_expiry_is_allowed_without_a_cap(self, auth_client, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=0)
        client: TestClient = await auth_client(permissions=["manage:api_keys"])

        resp = await client.post("/api/v1/web/admin/api-keys/", json={"name": "CI Key"})

        assert resp.status_code == 201, resp.text
        assert resp.json()["expires_at"] is None


async def test_list_api_keys(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    await _create(client)
    resp = await client.get("/api/v1/web/admin/api-keys/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(k["name"] == "CI Key" for k in body["items"])


async def test_list_api_keys_requires_manage_permission(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.get("/api/v1/web/admin/api-keys/")
    assert resp.status_code == 403


async def test_revoke_api_key(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    created = await _create(client)
    resp = await client.post(f"/api/v1/web/admin/api-keys/{created['id']}/revoke")
    assert resp.status_code == 200
    body = resp.json()
    assert body["revoked_at"] is not None


async def test_revoke_all_api_keys(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    await _create(client, name="Key One")
    await _create(client, name="Key Two")
    resp = await client.post("/api/v1/web/admin/api-keys/revoke-all")
    assert resp.status_code == 200
    assert resp.json()["revoked_count"] == 2


async def test_read_api_key_usage_log(auth_client) -> None:
    """The usage-log sub-resource: this router's own distinguishing feature
    beyond plain CRUD. No calls have been logged against a freshly created
    key, so the list is empty but the route + use case must still resolve."""
    client: TestClient = await auth_client(permissions=["manage:api_keys"])
    created = await _create(client)
    resp = await client.get(f"/api/v1/web/admin/api-keys/{created['id']}/usage-log")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ── Pagination / sort / search ──────────────────────────────────────────


class TestPagination:
    async def test_limit_caps_the_page_but_not_the_total(self, auth_client) -> None:
        client: TestClient = await auth_client(permissions=["manage:api_keys"])
        await _create(client, name="Alpha")
        await _create(client, name="Beta")
        await _create(client, name="Gamma")

        body = (await client.get("/api/v1/web/admin/api-keys/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, auth_client) -> None:
        client: TestClient = await auth_client(permissions=["manage:api_keys"])
        await _create(client, name="Alpha")
        await _create(client, name="Beta")
        await _create(client, name="Gamma")

        first = (await client.get("/api/v1/web/admin/api-keys/?limit=2")).json()
        second = (await client.get("/api/v1/web/admin/api-keys/?skip=2&limit=2")).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_a_bare_request_does_not_return_the_whole_table(self, auth_client, db) -> None:
        """Regression guard: an omitted `limit` goes through
        `ApiKeyFilterParams` -> `clamp_page` to DEFAULT_PAGE_SIZE=100, not
        a hardcoded 50 declared on the handler. Seeded
        directly via the ORM, including one throwaway backing user per key
        (api_key_table.user_id is unique, mirroring CreateApiKey's real
        "one service-account per key" invariant) rather than 100+ live
        requests.
        """
        client: TestClient = await auth_client(permissions=["manage:api_keys"])
        now = (await client.get("/api/v1/web/admin/api-keys/")).json()
        assert now["total"] == 0

        row_count = DEFAULT_PAGE_SIZE + 4
        created = datetime.now(UTC)
        backing_users = [
            UserOrmModel(
                username=f"api-key-backing-{i}",
                full_name=f"API Key Backing {i}",
                email=f"api-key-backing-{i}@example.com",
                hashed_password="x",
                created=created,
            )
            for i in range(row_count)
        ]
        db.add_all(backing_users)
        await db.flush()

        db.add_all(
            ApiKeyOrmModel(
                name=f"Key {i}",
                token_hash=f"hash-{i}",
                token_prefix="key_",
                user_id=user.id,
                created_by_id=user.id,
                created=created,
            )
            for i, user in enumerate(backing_users)
        )
        await db.commit()

        body = (await client.get("/api/v1/web/admin/api-keys/")).json()

        assert body["total"] == row_count
        assert len(body["items"]) == DEFAULT_PAGE_SIZE


class TestSortingAndSearch:
    async def test_sorts_by_name(self, auth_client) -> None:
        client: TestClient = await auth_client(permissions=["manage:api_keys"])
        await _create(client, name="Zeta")
        await _create(client, name="Alpha")
        await _create(client, name="Mike")

        asc = (await client.get("/api/v1/web/admin/api-keys/?order_by=name&order_dir=asc")).json()
        names = [i["name"] for i in asc["items"]]
        assert names == sorted(names)

        desc = (await client.get("/api/v1/web/admin/api-keys/?order_by=name&order_dir=desc")).json()
        names = [i["name"] for i in desc["items"]]
        assert names == sorted(names, reverse=True)

    async def test_default_order_is_id_descending(self, auth_client) -> None:
        """Without `order_by` the list is ordered by id, newest first."""
        client: TestClient = await auth_client(permissions=["manage:api_keys"])
        first = await _create(client, name="First")
        second = await _create(client, name="Second")

        body = (await client.get("/api/v1/web/admin/api-keys/")).json()

        assert [i["id"] for i in body["items"]] == [second["id"], first["id"]]

    async def test_search_narrows_the_total(self, auth_client) -> None:
        client: TestClient = await auth_client(permissions=["manage:api_keys"])
        await _create(client, name="Deployment Key")
        await _create(client, name="Laptop Token")
        await _create(client, name="Deployment Backup")

        body = (await client.get("/api/v1/web/admin/api-keys/?search=Deployment")).json()

        assert body["total"] == 2
        assert {i["name"] for i in body["items"]} == {"Deployment Key", "Deployment Backup"}
