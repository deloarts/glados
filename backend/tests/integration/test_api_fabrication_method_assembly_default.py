"""
HTTP-level coverage for FabricationMethod.default_for_assemblies: at most
one method carries it, setting it moves it off the previous holder,
archiving clears it, GET /web/fabrication-methods/assembly-default serves
the holder, and the PAT surface exposes the flag for the SolidWorks add-in.
The partial unique index behind the single default is checked on SQLite
through the repository.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.errors import FabricationMethodAssemblyDefaultConflictError
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission

BASE_URL = "/api/v1/web/fabrication-methods"
DEFAULT_URL = f"{BASE_URL}/assembly-default"


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="assembly-default-pat-owner",
        email="assembly-default-pat-owner@example.com",
        permissions=[Permission.WRITE_PAT],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[], Awaitable[str]]:
    async def _mint() -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="assembly-default-test-pat", permissions=[]),
        )
        return result.token

    return _mint


@pytest.fixture
async def method_editor(auth_client) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[
            Permission.WRITE_FABRICATION_METHODS,
        ]
    )


async def _create(client: httpx.AsyncClient, name: str, *, default: bool = False) -> int:
    resp = await client.post(
        BASE_URL + "/", json={"name": {"enGB": name}, "default_for_assemblies": default}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _flagged_ids(client: httpx.AsyncClient) -> list[int]:
    resp = await client.get(BASE_URL + "/", params={"include_archived": True})
    assert resp.status_code == 200, resp.text
    return [m["id"] for m in resp.json()["items"] if m["default_for_assemblies"]]


async def test_assembly_default_is_null_when_no_method_is_flagged(
    method_editor: httpx.AsyncClient,
) -> None:
    await _create(method_editor, "Milling")
    resp = await method_editor.get(DEFAULT_URL)
    assert resp.status_code == 200, resp.text
    assert resp.json() is None


async def test_flag_moves_to_the_newest_holder_and_the_endpoint_follows(
    method_editor: httpx.AsyncClient,
) -> None:
    welding = await _create(method_editor, "Welding", default=True)
    assembly = await _create(method_editor, "Assembly", default=True)
    assert await _flagged_ids(method_editor) == [assembly]
    assert (await method_editor.get(DEFAULT_URL)).json()["id"] == assembly

    moved = await method_editor.put(
        f"{BASE_URL}/{welding}", json={"name": {"enGB": "Welding"}, "default_for_assemblies": True}
    )
    assert moved.status_code == 200, moved.text
    assert await _flagged_ids(method_editor) == [welding]
    assert (await method_editor.get(DEFAULT_URL)).json()["id"] == welding

    changelog = (await method_editor.get(f"{BASE_URL}/{assembly}/changelog")).json()
    assert "No longer the default for assemblies." in changelog[-1]


async def test_archiving_the_default_leaves_no_default(method_editor: httpx.AsyncClient) -> None:
    assembly = await _create(method_editor, "Assembly", default=True)
    archived = await method_editor.post(f"{BASE_URL}/{assembly}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["default_for_assemblies"] is False
    assert (await method_editor.get(DEFAULT_URL)).json() is None


async def test_archived_method_cannot_become_the_default(method_editor: httpx.AsyncClient) -> None:
    welding = await _create(method_editor, "Welding")
    assert (await method_editor.post(f"{BASE_URL}/{welding}/archive")).status_code == 200
    resp = await method_editor.put(
        f"{BASE_URL}/{welding}", json={"name": {"enGB": "Welding"}, "default_for_assemblies": True}
    )
    assert resp.status_code == 409, resp.text
    assert await _flagged_ids(method_editor) == []


async def test_pat_surface_exposes_the_flag(
    method_editor: httpx.AsyncClient, mint_pat: Callable[[], Awaitable[str]]
) -> None:
    assembly = await _create(method_editor, "Assembly", default=True)
    headers = {"X-Api-Key": await mint_pat()}

    single = await method_editor.get(f"/api/v1/pat/fabrication-methods/{assembly}", headers=headers)
    assert single.status_code == 200, single.text
    assert single.json()["default_for_assemblies"] is True

    lookups = await method_editor.get("/api/v1/pat/lookups/", headers=headers)
    assert lookups.status_code == 200, lookups.text
    flagged = [
        m["id"] for m in lookups.json()["fabrication_methods"] if m["default_for_assemblies"]
    ]
    assert flagged == [assembly]


async def test_unique_index_rejects_a_second_flagged_method(
    db: AsyncSession, create_user: Callable[..., Awaitable[User]]
) -> None:
    """Bypasses the use cases, which move the flag first, to show the
    index itself holds the single default on SQLite."""
    creator = await create_user(username="assembly-default-creator")
    repo = SqlAlchemyFabricationMethodRepository(db)

    def flagged(name: str) -> FabricationMethod:
        now = datetime.now(UTC)
        return FabricationMethod(
            id=0,
            created=now,
            changed=now,
            changes=[],
            name=LocalizedText({"enGB": name}),
            label_color="#999999",
            label_font_color="#000000",
            description=LocalizedText(),
            creator_id=creator.id,
            default_for_assemblies=True,
        )

    await repo.save(flagged("Welding"))
    with pytest.raises(FabricationMethodAssemblyDefaultConflictError):
        await repo.save(flagged("Assembly"))
    await db.rollback()
