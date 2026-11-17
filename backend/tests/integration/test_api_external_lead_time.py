"""
HTTP-level coverage for the external lead-time fields added to
fabrication methods and suppliers: FabricationMethodResponse.lead_time_days
and SupplierResponse.external_lead_time_days round-trip through the web
create/update endpoints, and stay off the PAT surface (the SolidWorks
add-in never reads or sets them), following the pattern
test_api_suppliers.py and test_api_fabrication_methods_pagination.py
already use for this pair of resources.
"""

from collections.abc import Awaitable
from collections.abc import Callable

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
from tests.integration._edit_versions import row_version


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="lead-time-pat-owner",
        email="lead-time-pat-owner@example.com",
        permissions=[Permission.WRITE_PAT],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="lead-time-test-pat", permissions=permissions),
        )
        return result.token

    return _mint


async def test_fabrication_method_lead_time_days_round_trips_through_create_and_update(
    auth_client,
) -> None:
    client = await auth_client(permissions=[Permission.WRITE_FABRICATION_METHODS])

    created = await client.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": "Anodizing"}, "required_external": True, "lead_time_days": 5},
    )
    assert created.status_code == 201, created.text
    assert created.json()["lead_time_days"] == 5

    updated = await client.put(
        f"/api/v1/web/fabrication-methods/{created.json()['id']}",
        json={"name": {"enGB": "Anodizing"}, "required_external": True, "lead_time_days": 8},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["lead_time_days"] == 8

    fetched = await client.get(f"/api/v1/web/fabrication-methods/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["lead_time_days"] == 8


async def test_supplier_external_lead_time_days_round_trips_through_create_and_update(
    auth_client,
) -> None:
    client = await auth_client(permissions=[Permission.WRITE_SUPPLIERS])

    created = await client.post(
        "/api/v1/web/suppliers/",
        json={"name": "Acme Fasteners", "level": "B", "external_lead_time_days": 3},
    )
    assert created.status_code == 201, created.text
    assert created.json()["external_lead_time_days"] == 3

    updated = await client.put(
        f"/api/v1/web/suppliers/{created.json()['id']}",
        json={
            "expected_edit_version": await row_version(
                client, f"/api/v1/web/suppliers/{created.json()['id']}"
            ),
            "name": "Acme Fasteners",
            "level": "B",
            "external_lead_time_days": 6,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["external_lead_time_days"] == 6

    fetched = await client.get(f"/api/v1/web/suppliers/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["external_lead_time_days"] == 6


async def test_pat_surface_never_exposes_fabrication_method_lead_time_days(
    auth_client, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """The PAT contract is frozen and deliberately keeps this field off it;
    the SolidWorks add-in has no use for a scheduling forecast input."""
    web_client = await auth_client(permissions=[Permission.WRITE_FABRICATION_METHODS])
    created = await web_client.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": "Heat Treatment"}, "required_external": True, "lead_time_days": 4},
    )
    assert created.status_code == 201, created.text

    token = await mint_pat([])
    pat_resp = await web_client.get(
        f"/api/v1/pat/fabrication-methods/{created.json()['id']}",
        headers={"X-Api-Key": token},
    )
    assert pat_resp.status_code == 200
    assert "lead_time_days" not in pat_resp.json()


async def test_pat_surface_never_exposes_supplier_external_lead_time_days(
    auth_client, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    web_client = await auth_client(permissions=[Permission.WRITE_SUPPLIERS])
    created = await web_client.post(
        "/api/v1/web/suppliers/",
        json={"name": "Beta Metals", "level": "A", "external_lead_time_days": 7},
    )
    assert created.status_code == 201, created.text

    token = await mint_pat([])
    pat_resp = await web_client.get(
        f"/api/v1/pat/suppliers/{created.json()['id']}",
        headers={"X-Api-Key": token},
    )
    assert pat_resp.status_code == 200
    assert "external_lead_time_days" not in pat_resp.json()
