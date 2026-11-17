"""
HTTP-level coverage of GET /api/v1/web/users/me/personal-access-tokens/:
the list route follows the `PatFilterParams`-shaped convention every other
paginated resource follows, so an *omitted* `limit` resolves to
`DEFAULT_PAGE_SIZE` (100) and `search`/`order_by`/`order_dir` are
supported. Follows test_api_customer_crud.py's `TestList` block as the
declared template for the pagination vertical.

Tokens are minted through the real CreatePat use case, never a hand-built
row, except for the bulk seed below (mirrors test_api_customer_crud.py's
own reasoning: a pagination-cap check does not need 100+ live HTTP round
trips).
"""

from datetime import UTC
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatOrmModel
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import TEST_PASSWORD

WRITE_PAT = [Permission.WRITE_PAT]


@pytest.fixture
async def owner(auth_client, seeded_security):
    return await auth_client(permissions=WRITE_PAT)


async def _create(client: TestClient, **overrides: object) -> dict:
    body = {"name": "CI Token", "password": TEST_PASSWORD} | overrides
    resp = await client.post("/api/v1/web/users/me/personal-access-tokens/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestList:
    async def test_empty_list_has_a_zero_total(self, owner):
        body = (await owner.get("/api/v1/web/users/me/personal-access-tokens/")).json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_lists_everything_created(self, owner):
        await _create(owner, name="Alpha")
        await _create(owner, name="Beta")
        await _create(owner, name="Gamma")

        body = (await owner.get("/api/v1/web/users/me/personal-access-tokens/")).json()

        assert body["total"] == 3
        assert {i["name"] for i in body["items"]} == {"Alpha", "Beta", "Gamma"}

    async def test_limit_caps_the_page_but_not_the_total(self, owner):
        await _create(owner, name="Alpha")
        await _create(owner, name="Beta")
        await _create(owner, name="Gamma")

        body = (await owner.get("/api/v1/web/users/me/personal-access-tokens/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, owner):
        await _create(owner, name="Alpha")
        await _create(owner, name="Beta")
        await _create(owner, name="Gamma")

        first = (await owner.get("/api/v1/web/users/me/personal-access-tokens/?limit=2")).json()
        second = (
            await owner.get("/api/v1/web/users/me/personal-access-tokens/?skip=2&limit=2")
        ).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_an_explicit_limit_above_the_max_is_rejected(self, owner):
        response = await owner.get(
            f"/api/v1/web/users/me/personal-access-tokens/?limit={MAX_PAGE_SIZE + 1}"
        )
        assert response.status_code == 422

    async def test_a_bare_request_does_not_return_the_whole_table(self, owner, db):
        """Before this, an omitted `limit` fell back to a hardcoded 50 (not
        DEFAULT_PAGE_SIZE=100) because the handler declared `limit: int =
        Query(default=50, ...)` directly rather than going through
        `PatFilterParams` -> `clamp_page`. Seeded directly via the ORM
        rather than 100+ live requests, like the customer-vertical
        original.
        """
        now = (await owner.get("/api/v1/web/users/me/personal-access-tokens/")).json()
        assert now["total"] == 0

        # The owner fixture is the only user created so far, so id=1.
        row_count = DEFAULT_PAGE_SIZE + 4
        created = datetime.now(UTC)
        db.add_all(
            PatOrmModel(
                name=f"Token {i}",
                token_hash=f"hash-{i}",
                token_prefix="pat_",
                user_id=1,
                created=created,
            )
            for i in range(row_count)
        )
        await db.commit()

        body = (await owner.get("/api/v1/web/users/me/personal-access-tokens/")).json()

        assert body["total"] == row_count
        assert len(body["items"]) == DEFAULT_PAGE_SIZE


class TestRevocation:
    async def test_include_revoked_false_hides_revoked_tokens_by_default(self, owner):
        created = await _create(owner, name="Doomed")
        await owner.post(f"/api/v1/web/users/me/personal-access-tokens/{created['id']}/revoke")

        body = (await owner.get("/api/v1/web/users/me/personal-access-tokens/")).json()

        assert body["total"] == 0

    async def test_include_revoked_true_shows_revoked_tokens(self, owner):
        created = await _create(owner, name="Doomed")
        await owner.post(f"/api/v1/web/users/me/personal-access-tokens/{created['id']}/revoke")

        body = (
            await owner.get("/api/v1/web/users/me/personal-access-tokens/?include_revoked=true")
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["revoked_at"] is not None


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

    async def test_expires_in_days_above_the_cap_is_rejected(self, owner, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=30)

        resp = await owner.post(
            "/api/v1/web/users/me/personal-access-tokens/",
            json={"name": "CI Token", "expires_in_days": 31, "password": TEST_PASSWORD},
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "TokenLifetimeExceededError"

    async def test_expires_in_days_at_the_cap_boundary_succeeds(self, owner, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=30)

        resp = await owner.post(
            "/api/v1/web/users/me/personal-access-tokens/",
            json={"name": "CI Token", "expires_in_days": 30, "password": TEST_PASSWORD},
        )

        assert resp.status_code == 201, resp.text

    async def test_no_expiry_is_refused_while_a_cap_is_set(self, owner, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=1)

        resp = await owner.post(
            "/api/v1/web/users/me/personal-access-tokens/",
            json={"name": "CI Token", "password": TEST_PASSWORD},
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "TokenExpiryRequiredError"

    async def test_no_expiry_is_allowed_without_a_cap(self, owner, db) -> None:
        await self._seed_cap(db, token_max_lifetime_days=0)

        resp = await owner.post(
            "/api/v1/web/users/me/personal-access-tokens/",
            json={"name": "CI Token", "password": TEST_PASSWORD},
        )

        assert resp.status_code == 201, resp.text
        assert resp.json()["expires_at"] is None


class TestSortingAndSearch:
    async def test_sorts_by_name(self, owner):
        await _create(owner, name="Zeta")
        await _create(owner, name="Alpha")
        await _create(owner, name="Mike")

        asc = (
            await owner.get(
                "/api/v1/web/users/me/personal-access-tokens/?order_by=name&order_dir=asc"
            )
        ).json()
        names = [i["name"] for i in asc["items"]]
        assert names == sorted(names)

        desc = (
            await owner.get(
                "/api/v1/web/users/me/personal-access-tokens/?order_by=name&order_dir=desc"
            )
        ).json()
        names = [i["name"] for i in desc["items"]]
        assert names == sorted(names, reverse=True)

    async def test_default_order_is_id_descending(self, owner):
        """Without `order_by` the list is ordered by id, newest first."""
        first = await _create(owner, name="First")
        second = await _create(owner, name="Second")

        body = (await owner.get("/api/v1/web/users/me/personal-access-tokens/")).json()

        assert [i["id"] for i in body["items"]] == [second["id"], first["id"]]

    async def test_search_narrows_the_total(self, owner):
        await _create(owner, name="Deployment Key")
        await _create(owner, name="Laptop Token")
        await _create(owner, name="Deployment Backup")

        body = (
            await owner.get("/api/v1/web/users/me/personal-access-tokens/?search=Deployment")
        ).json()

        assert body["total"] == 2
        assert {i["name"] for i in body["items"]} == {"Deployment Key", "Deployment Backup"}
