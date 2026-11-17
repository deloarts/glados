"""
HTTP-level coverage of the source item catalogue's PAT surface:
GET/POST /api/v1/pat/source-items/ and GET /api/v1/pat/source-items/{id}.
The add-in creates source items directly (raw-material specs it
discovers in CAD have no other path into Glados); update/archive/restore
stay web-only, so this router only ever needs list, create and read.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

SOURCE_ITEMS_URL = "/api/v1/pat/source-items/"

MintPat = Callable[[list[str]], Awaitable[str]]


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="source-items-pat-owner",
        email="source-items-pat-owner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.WRITE_SOURCE_ITEMS],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> MintPat:
    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="source-items-test-pat", permissions=permissions),
        )
        return result.token

    return _mint


@pytest.fixture
async def source_item_type_id(auth_client) -> int:
    writer = await auth_client(permissions=[Permission.WRITE_SOURCE_ITEM_TYPES])
    created = (
        await writer.post("/api/v1/web/source-item-types/", json={"name": {"enGB": "Round bar"}})
    ).json()
    return created["id"]


async def test_requires_a_valid_pat(client: httpx.AsyncClient) -> None:
    assert (await client.get(SOURCE_ITEMS_URL)).status_code == 401


async def test_list_requires_no_special_permission(
    client: httpx.AsyncClient, mint_pat: MintPat
) -> None:
    token = await mint_pat([])
    resp = await client.get(SOURCE_ITEMS_URL, headers={"X-Api-Key": token})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_create_requires_write_permission(
    client: httpx.AsyncClient,
    mint_pat: MintPat,
    source_item_type_id: int,
) -> None:
    token = await mint_pat([])
    resp = await client.post(
        SOURCE_ITEMS_URL,
        json={"type_id": source_item_type_id, "material": "1.0037"},
        headers={"X-Api-Key": token},
    )
    assert resp.status_code == 403


async def test_create_and_read_round_trip(
    client: httpx.AsyncClient,
    mint_pat: MintPat,
    source_item_type_id: int,
) -> None:
    token = await mint_pat([Permission.WRITE_SOURCE_ITEMS])

    created = await client.post(
        SOURCE_ITEMS_URL,
        json={
            "type_id": source_item_type_id,
            "material": "1.0037",
            "dimension": "40mm",
        },
        headers={"X-Api-Key": token},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["type_id"] == source_item_type_id
    assert body["material"] == "1.0037"
    assert body["id"] > 0

    read = await client.get(f"{SOURCE_ITEMS_URL}{body['id']}", headers={"X-Api-Key": token})
    assert read.status_code == 200
    assert read.json()["id"] == body["id"]

    listed = await client.get(SOURCE_ITEMS_URL, headers={"X-Api-Key": token})
    assert listed.status_code == 200
    assert any(i["id"] == body["id"] for i in listed.json()["items"])


async def test_read_missing_is_404(client: httpx.AsyncClient, mint_pat: MintPat) -> None:
    token = await mint_pat([])
    resp = await client.get(f"{SOURCE_ITEMS_URL}999999", headers={"X-Api-Key": token})
    assert resp.status_code == 404


async def test_duplicate_spec_is_rejected(
    client: httpx.AsyncClient,
    mint_pat: MintPat,
    source_item_type_id: int,
) -> None:
    token = await mint_pat([Permission.WRITE_SOURCE_ITEMS])
    payload = {"type_id": source_item_type_id, "material": "1.0037", "dimension": "40mm"}

    first = await client.post(SOURCE_ITEMS_URL, json=payload, headers={"X-Api-Key": token})
    assert first.status_code == 201

    second = await client.post(SOURCE_ITEMS_URL, json=payload, headers={"X-Api-Key": token})
    assert second.status_code == 409
