"""
Authentication and authorization enforced through the real HTTP stack.

Every assertion here is about a boundary that unit tests structurally
cannot reach: whether the `Depends(get_current_active_user)` chain is
actually wired onto a route, and whether a domain exception raised deep
in a use case surfaces as the right HTTP status. A route accidentally
shipped without its auth dependency, or an unregistered exception type
falling through to a 500, both pass every unit test in this repo and
would only ever be caught here.
"""

from datetime import timedelta

import pytest

from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.token import create_access_token
from src.modules.platform.infrastructure.security.token import create_partial_token

from .conftest import auth_headers

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/web/users/me"),
    ("GET", "/api/v1/web/users/"),
    ("GET", "/api/v1/web/customers/"),
    ("GET", "/api/v1/web/projects/"),
]


# ── Unauthenticated access ────────────────────────────────────────────


class TestUnauthenticatedAccess:
    @pytest.mark.smoke
    async def test_health_is_public(self, client):
        assert (await client.get("/health")).status_code == 200

    async def test_api_responses_carry_security_headers(self, client):
        """Verified through the real stack: SecurityHeadersMiddleware
        is actually wired into create_app(), not just unit-tested in
        isolation."""
        response = await client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_protected_endpoints_reject_a_missing_token(self, client):
        for method, path in PROTECTED_ENDPOINTS:
            response = await client.request(method, path)
            assert response.status_code == 401, f"{method} {path} did not require auth"

    async def test_protected_endpoints_reject_a_garbage_token(self, client):
        client.headers.update({"Authorization": "Bearer not-a-jwt"})
        for method, path in PROTECTED_ENDPOINTS:
            assert (await client.request(method, path)).status_code == 401

    async def test_rejects_a_token_signed_with_the_wrong_key(self, client, create_user):
        """Web tokens are non-persistent; a persistent-key token must not
        be accepted on the web surface."""
        user = await create_user()
        token = create_access_token(
            subject=user.id, persistent=True, expires_delta=timedelta(minutes=5)
        )
        client.headers.update({"Authorization": f"Bearer {token}"})
        assert (await client.get("/api/v1/web/users/me")).status_code == 401


# ── Token semantics ───────────────────────────────────────────────────


class TestTokenSemantics:
    async def test_valid_token_is_accepted(self, client, create_user):
        user = await create_user()
        client.headers.update(await auth_headers(user))

        response = await client.get("/api/v1/web/users/me")

        assert response.status_code == 200
        assert response.json()["username"] == user.username

    async def test_user_response_never_leaks_the_rfid_hash(self, client, create_user):
        """The stored HMAC of a low-entropy RFID UID stays in the database,
        the API exposes only a boolean, never the value."""
        user = await create_user()
        client.headers.update(await auth_headers(user))

        body = (await client.get("/api/v1/web/users/me")).json()

        assert "rfid_lookup" not in body
        assert body["rfid_configured"] is False

    async def test_totp_pending_token_cannot_access_protected_routes(self, client, create_user):
        """A half-authenticated TOTP challenge token must not work as a
        session token, this is the authentication-bypass case that
        test_security_token.py checks in isolation, verified here end to
        end through the real dependency chain."""
        user = await create_user()
        client.headers.update({"Authorization": f"Bearer {create_partial_token(user.id)}"})

        assert (await client.get("/api/v1/web/users/me")).status_code == 401

    async def test_token_for_a_deleted_user_is_rejected(self, client, create_user, db):
        user = await create_user()
        headers = await auth_headers(user)

        await SqlAlchemyUserRepository(db).delete(user)
        await db.commit()

        client.headers.update(headers)
        assert (await client.get("/api/v1/web/users/me")).status_code == 401

    async def test_stale_token_version_invalidates_the_session(self, client, create_user):
        """Force-logout works by bumping token_version, every token
        minted before the bump must stop working immediately."""
        user = await create_user()
        stale = create_access_token(
            subject=user.id,
            persistent=False,
            expires_delta=timedelta(minutes=5),
            token_version=user.token_version + 1,
        )
        client.headers.update({"Authorization": f"Bearer {stale}"})

        assert (await client.get("/api/v1/web/users/me")).status_code == 401

    async def test_inactive_user_is_rejected(self, client, create_user):
        user = await create_user(is_active=False)
        client.headers.update(await auth_headers(user))

        assert (await client.get("/api/v1/web/users/me")).status_code == 401


# ── Permission enforcement -> HTTP 403 ────────────────────────────────


CUSTOMER_PAYLOAD = {"name": "ACME", "level": "A"}


class TestPermissionEnforcement:
    async def test_creating_without_permission_is_403_not_500(self, auth_client):
        """InsufficientPermissionsError must be registered in
        exception_handlers.py, an unregistered domain error falls through
        as a 500, which no unit test would notice."""
        client = await auth_client(permissions=[])

        response = await client.post("/api/v1/web/customers/", json=CUSTOMER_PAYLOAD)

        assert response.status_code == 403

    async def test_creating_with_permission_succeeds(self, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PROJECTS])

        response = await client.post("/api/v1/web/customers/", json=CUSTOMER_PAYLOAD)

        assert response.status_code == 201

    async def test_archiving_requires_manage_not_just_write(self, auth_client):
        """CustomerRules.assert_can_archive checks MANAGE_PROJECTS while
        create/update only need WRITE_PROJECTS, an escalation boundary
        worth verifying over HTTP."""
        client = await auth_client(permissions=[Permission.WRITE_PROJECTS])
        created = (await client.post("/api/v1/web/customers/", json=CUSTOMER_PAYLOAD)).json()

        assert (
            await client.post(f"/api/v1/web/customers/{created['id']}/archive")
        ).status_code == 403

    async def test_archiving_with_manage_permission_succeeds(self, auth_client):
        client = await auth_client(
            permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]
        )
        created = (await client.post("/api/v1/web/customers/", json=CUSTOMER_PAYLOAD)).json()

        assert (
            await client.post(f"/api/v1/web/customers/{created['id']}/archive")
        ).status_code == 200


# ── Domain exception -> HTTP status mapping ───────────────────────────


class TestExceptionStatusMapping:
    async def test_missing_customer_maps_to_404(self, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PROJECTS])
        assert (await client.get("/api/v1/web/customers/999999")).status_code == 404

    async def test_updating_a_missing_customer_maps_to_404(self, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PROJECTS])
        response = await client.put(
            "/api/v1/web/customers/999999",
            json={"name": "X", "level": "A", "expected_edit_version": 0},
        )
        assert response.status_code == 404

    async def test_archiving_a_missing_customer_maps_to_404(self, auth_client):
        client = await auth_client(
            permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]
        )
        assert (await client.post("/api/v1/web/customers/999999/archive")).status_code == 404

    async def test_no_endpoint_returns_a_500_for_these_flows(self, auth_client):
        """Blanket guard: every status asserted above is a deliberate
        mapping, so nothing in this file should ever produce a 5xx."""
        client = await auth_client(permissions=[])
        for method, path in PROTECTED_ENDPOINTS:
            assert (await client.request(method, path)).status_code < 500
