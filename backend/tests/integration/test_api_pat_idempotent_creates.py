"""The pat creates of bought items take an Idempotency-Key: the add-in sends
one per user action, so a retry after a lost answer is answered with the
item the first request created, and no second item and no second part
number come of it."""

from collections.abc import Awaitable
from collections.abc import Callable

import httpx
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

BOUGHT_ITEMS = "/api/v1/pat/bought-items/"


async def _pat(db: AsyncSession, create_user: Callable[..., Awaitable[User]]) -> str:
    owner = await create_user(
        username="addin-user",
        email="addin-user@example.com",
        permissions=[Permission.WRITE_PAT, Permission.WRITE_BOUGHT_ITEMS],
    )
    created = await CreatePat(
        SqlAlchemyPatRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(
        actor=owner, cmd=CreatePatCommand(name="addin", permissions=[Permission.WRITE_BOUGHT_ITEMS])
    )
    return created.token


async def _supplier(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> int:
    web = await auth_client(permissions=[Permission.WRITE_SUPPLIERS])
    created = await web.post("/api/v1/web/suppliers/", json={"name": "Retry AG", "level": "B"})
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


async def test_a_retried_create_with_the_same_key_creates_one_item(
    db: AsyncSession, client: httpx.AsyncClient, create_user, auth_client
) -> None:
    supplier_id = await _supplier(auth_client)
    headers = {"X-Api-Key": await _pat(db, create_user), "Idempotency-Key": "addin-action-1"}
    body = {"order_code_1": "RETRY-1", "article_name": "Retried", "manufacturer_id": supplier_id}

    first = await client.post(BOUGHT_ITEMS, json=body, headers=headers)
    again = await client.post(BOUGHT_ITEMS, json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert again.status_code == 201, again.text
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["part_number"] == first.json()["part_number"]
    listed = await client.get(
        BOUGHT_ITEMS, params={"search": "RETRY-1"}, headers={"X-Api-Key": headers["X-Api-Key"]}
    )
    assert listed.json()["total"] == 1


async def test_a_new_key_creates_a_new_item(
    db: AsyncSession, client: httpx.AsyncClient, create_user, auth_client
) -> None:
    supplier_id = await _supplier(auth_client)
    token = await _pat(db, create_user)
    body = {"order_code_1": "RETRY-2", "article_name": "Twice", "manufacturer_id": supplier_id}

    first = await client.post(
        BOUGHT_ITEMS, json=body, headers={"X-Api-Key": token, "Idempotency-Key": "a"}
    )
    second = await client.post(
        BOUGHT_ITEMS, json=body, headers={"X-Api-Key": token, "Idempotency-Key": "b"}
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]
