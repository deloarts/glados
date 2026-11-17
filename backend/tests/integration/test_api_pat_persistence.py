"""
Proves that the personal access token routes persist what they report.
Creating a token, revoking one and revoking all of them are each read back
through a separate request, so a use case that forgets to commit its unit
of work fails here instead of silently losing the write.
"""

from typing import Any

import pytest

from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import TEST_PASSWORD

PATS = "/api/v1/web/users/me/personal-access-tokens"


@pytest.fixture
async def owner(auth_client, seeded_security) -> Any:
    return await auth_client(permissions=[Permission.WRITE_PAT])


async def _create(client: Any, name: str) -> dict[str, Any]:
    response = await client.post(f"{PATS}/", json={"name": name, "password": TEST_PASSWORD})
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_created_pat_is_persisted_and_authenticates(owner, client) -> None:
    created = await _create(owner, "persisted")

    reread = await owner.get(f"{PATS}/{created['id']}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["name"] == "persisted"

    me = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": created["token"]})
    assert me.status_code == 200, me.text


async def test_revoked_pat_stays_revoked(owner, client) -> None:
    created = await _create(owner, "to revoke")

    revoked = await owner.post(f"{PATS}/{created['id']}/revoke")
    assert revoked.status_code == 200, revoked.text

    reread = await owner.get(f"{PATS}/{created['id']}")
    assert reread.json()["revoked_at"] is not None
    me = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": created["token"]})
    assert me.status_code == 401


async def test_revoke_all_is_persisted(owner) -> None:
    first = await _create(owner, "first")
    second = await _create(owner, "second")

    response = await owner.post(f"{PATS}/revoke-all")
    assert response.status_code == 200, response.text
    assert response.json()["revoked_count"] == 2

    for created in (first, second):
        reread = await owner.get(f"{PATS}/{created['id']}")
        assert reread.json()["revoked_at"] is not None
