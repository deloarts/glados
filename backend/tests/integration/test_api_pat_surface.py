"""
HTTP-level coverage of the personal-access-token (PAT) authentication
surface. `pat/router.py` mounts 13 routers (made-items, source-items,
inspection-methods, lookups and others) behind `get_current_user_pat`,
each resolved per-route (not at router level).

Tokens are minted through the real `CreatePat`/`RevokePat` use cases
against the throwaway SQLite DB (`db` fixture), never a hand-built row,
so a broken use case would fail these tests too, not just a broken route.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.application.use_cases.pat.revoke_pat import RevokePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.pat import hash_pat

# Every PAT router, and one route on it that needs no seed data to reach
# either a 401 (missing credential, checked before the route body runs at
# all) or a 200 (an empty-but-valid paginated list). `/users` has no list
# route, `/me` is its equivalent.
_PAT_LIST_ROUTES = [
    "/api/v1/pat/bought-items/",
    "/api/v1/pat/products/",
    "/api/v1/pat/projects/",
    "/api/v1/pat/suppliers/",
    "/api/v1/pat/article-groups/",
    "/api/v1/pat/fabrication-methods/",
    "/api/v1/pat/inspection-methods/",
    "/api/v1/pat/made-items/",
    "/api/v1/pat/source-item-types/",
    "/api/v1/pat/source-items/",
    "/api/v1/pat/lookups/",
    "/api/v1/pat/users/me",
]


@pytest.fixture
async def pat_owner(create_user) -> User:
    """Holds every permission a test in this file needs to grant to a PAT
    it mints (assert_requested_permissions_allowed forbids granting a
    permission the creator doesn't hold themselves)."""
    return await create_user(
        username="pat-owner",
        email="pat-owner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.WRITE_BOUGHT_ITEMS],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    """Mints a real PAT via CreatePat, scoped to `permissions`, and returns
    the raw token (visible only at creation)."""

    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="test-pat", permissions=permissions),
        )
        return result.token

    return _mint


async def test_pat_routers_reject_missing_credential(client: httpx.AsyncClient) -> None:
    """(i) No credential -> 401 on one route of every one of the 9 mounted
    PAT routers. The cheapest possible proof every mount actually resolves
    and is actually guarded: deleting `Depends(get_current_user_pat)` from
    any of these endpoint modules turns its assertion red."""
    for path in _PAT_LIST_ROUTES:
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} did not reject a missing PAT: {resp.text}"


@pytest.mark.smoke
async def test_valid_pat_reads_succeed(
    client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """(ii) A valid, unrevoked PAT reaches the route body: reads on this
    surface carry no per-route permission check beyond "is an authenticated
    PAT holder", so an empty-permission token still gets 200."""
    token = await mint_pat([])
    resp = await client.get("/api/v1/pat/bought-items/", headers={"X-Api-Key": token})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_revoked_pat_is_rejected(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    """(iii) A revoked PAT is a 401, not merely "no longer privileged"."""
    token = await mint_pat([])
    created = await CreatePat(
        SqlAlchemyPatRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(actor=pat_owner, cmd=CreatePatCommand(name="throwaway", permissions=[]))
    await RevokePat(SqlAlchemyPatRepository(db), uow=SqlAlchemyUnitOfWork(db)).execute(
        actor=pat_owner, pat_id=created.id
    )

    resp = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": created.token})
    assert resp.status_code == 401
    # The freshly minted (still-valid) token from the fixture is untouched,
    # confirms the 401 above is about revocation, not a bad header shape.
    resp_ok = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": token})
    assert resp_ok.status_code == 200


async def test_expired_pat_is_rejected(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    """(iii-b) An expired PAT is a 401, not merely "no longer privileged".

    PersonalAccessToken.is_expired compares a fetched `expires_at` against
    `datetime.now(UTC)`. SQLite's DateTime(timezone=True) round trip yields
    a naive value after a session.refresh(), which would crash that
    comparison with "can't compare offset-naive and offset-aware
    datetimes", so pat_repository.py's `_orm_to_entity` stamps UTC back on,
    the same `_aware()` pattern admin_settings_repository.py uses for the
    banner's datetime columns.
    """
    token = await mint_pat([])
    repo = SqlAlchemyPatRepository(db)
    stored = await repo.get_by_token_hash(hash_pat(token))
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(days=1)
    await repo.save(stored)
    await db.commit()

    resp = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": token})

    assert resp.status_code == 401


async def test_pat_lacking_permission_is_rejected(
    client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """(iv) A valid PAT scoped to no permissions is still turned away by a
    route's own domain-rule check. Unlike the reads above, POST
    /bought-items goes through CreateBoughtItem, which asserts
    write:bought_items on the *token's* scope (ValidatePat caps the
    effective user at token.permissions, not the owner's)."""
    token = await mint_pat([])
    resp = await client.post(
        "/api/v1/pat/bought-items/",
        headers={"X-Api-Key": token},
        json={
            "order_code_1": "TEST-1",
            "article_name": "Test article",
            "manufacturer_id": 1,
        },
    )
    assert resp.status_code == 403


# ── made-items (Part 1: PAT read surface, no write route by design,
# routing is CAD-authored per docs/FIELD_OWNERSHIP.md, see
# pat/endpoints/made_items.py's module docstring) ──────────────────────


async def _make_item(
    db: AsyncSession,
    creator_id: int,
    *,
    part_number: str,
    revision: str,
    vault_id: str | None = None,
    pdm_file_id: int | None = None,
    pdm_file_version: int | None = None,
    pdm_synced_at: datetime | None = None,
    pdm_sync_state: PdmSyncState | None = None,
    source_item_id: int | None = None,
    pdm_source_item_id: int | None = None,
) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            revision=revision,
            revision_date=None,
            revision_note=None,
            article_name="Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD if pdm_file_id is not None else DataSource.WEB,
            part_number=part_number,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=source_item_id,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
            vault_id=vault_id,
            pdm_file_id=pdm_file_id,
            pdm_file_version=pdm_file_version,
            pdm_synced_at=pdm_synced_at,
            pdm_sync_state=pdm_sync_state,
            pdm_source_item_id=pdm_source_item_id,
        )
    )
    await db.commit()
    return seeded


async def _make_fabrication_method(db: AsyncSession, creator_id: int) -> FabricationMethod:
    return await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Turning"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )


async def _make_process(
    db: AsyncSession,
    made_item_id: int,
    creator_id: int,
    fabrication_method_id: int,
    *,
    position: int,
    group_index: int,
) -> MadeItemProcess:
    return await SqlAlchemyMadeItemRepository(db).save_process(
        MadeItemProcess(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            creator_id=creator_id,
            fabrication_method_id=fabrication_method_id,
            made_item_id=made_item_id,
            position=position,
            group_index=group_index,
        )
    )


async def test_made_items_list_with_empty_permission_pat_is_empty(
    client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """Reads on this surface carry no per-route permission check (same
    posture as `test_valid_pat_reads_succeed` above)."""
    token = await mint_pat([])
    resp = await client.get("/api/v1/pat/made-items/", headers={"X-Api-Key": token})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_read_made_item_by_part_number_orders_process_groups(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    """Processes are seeded out of position order (position 1 before
    position 0) to prove the response reflects `position`, not insertion
    order, with `group_index` carried along correctly."""
    method = await _make_fabrication_method(db, pat_owner.id)
    item = await _make_item(db, pat_owner.id, part_number="PN-MADE-1", revision="A")
    await _make_process(db, item.id, pat_owner.id, method.id, position=1, group_index=0)
    await _make_process(db, item.id, pat_owner.id, method.id, position=0, group_index=0)
    await _make_process(db, item.id, pat_owner.id, method.id, position=2, group_index=1)

    token = await mint_pat([])
    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-1", headers={"X-Api-Key": token}
    )

    assert resp.status_code == 200, resp.text
    processes = resp.json()["processes"]
    assert [p["position"] for p in processes] == [0, 1, 2]
    assert [p["group_index"] for p in processes] == [0, 0, 1]


async def test_read_made_item_by_part_number_and_revision_exact_hit(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    older = await _make_item(db, pat_owner.id, part_number="PN-MADE-2", revision="A")
    await _make_item(db, pat_owner.id, part_number="PN-MADE-2", revision="B")

    token = await mint_pat([])
    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-2",
        params={"revision": "A"},
        headers={"X-Api-Key": token},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == older.id
    assert body["revision"] == "A"


async def test_read_made_item_by_part_number_without_revision_returns_newest(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    await _make_item(db, pat_owner.id, part_number="PN-MADE-3", revision="A")
    newest = await _make_item(db, pat_owner.id, part_number="PN-MADE-3", revision="B")

    token = await mint_pat([])
    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-3", headers={"X-Api-Key": token}
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == newest.id
    assert body["revision"] == "B"


async def test_read_made_item_by_part_number_unknown_revision_404(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    await _make_item(db, pat_owner.id, part_number="PN-MADE-4", revision="A")

    token = await mint_pat([])
    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-4",
        params={"revision": "Z"},
        headers={"X-Api-Key": token},
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "MadeItemNotFoundError"


async def test_read_made_item_by_part_number_unknown_part_number_404(
    client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])
    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-UNKNOWN", headers={"X-Api-Key": token}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "MadeItemNotFoundError"


# ── PDM link fields on the response ────────────────────────────────

_SYNCED_AT = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


async def _supplier(db: AsyncSession, creator_id: int) -> Supplier:
    saved = await SqlAlchemySupplierRepository(db).save(
        Supplier(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            name="Acme",
            legal_name=None,
            vat_id=None,
            level=SupplierLevel.B,
            capability_ids=[],
            article_group_ids=[],
            street=None,
            city=None,
            country=None,
            postal_code=None,
            email=None,
            phone=None,
            weblink=None,
            order_email=None,
            order_language=None,
            order_template=None,
            request_email=None,
            request_language=None,
            request_template=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _bought_item(
    db: AsyncSession,
    creator_id: int,
    manufacturer_id: int,
    *,
    order_code_1: str,
    vault_id: str | None = None,
    pdm_file_id: int | None = None,
    pdm_file_version: int | None = None,
    pdm_synced_at: datetime | None = None,
    pdm_sync_state: PdmSyncState | None = None,
) -> BoughtItem:
    saved = await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            article_name="Widget",
            order_code_1=order_code_1,
            order_code_2=None,
            gtin=None,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD if pdm_file_id is not None else DataSource.WEB,
            part_number=None,
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            manufacturer_id=manufacturer_id,
            article_group_ids=[],
            successor_item_id=None,
            vault_id=vault_id,
            pdm_file_id=pdm_file_id,
            pdm_file_version=pdm_file_version,
            pdm_synced_at=pdm_synced_at,
            pdm_sync_state=pdm_sync_state,
        )
    )
    await db.commit()
    return saved


async def test_pat_read_made_item_pdm_fields_null_for_web_row(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    item = await _make_item(db, pat_owner.id, part_number="PN-MADE-PDM-NULL", revision="A")
    token = await mint_pat([])

    resp = await client.get(f"/api/v1/pat/made-items/{item.id}", headers={"X-Api-Key": token})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vault_id"] is None
    assert body["pdm_file_id"] is None
    assert body["pdm_file_version"] is None
    assert body["pdm_synced_at"] is None
    assert body["pdm_sync_state"] is None
    assert body["pdm_source_item_id"] is None


async def test_pat_read_made_item_returns_pdm_link_fields(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    item = await _make_item(
        db,
        pat_owner.id,
        part_number="PN-MADE-PDM-LINK",
        revision="A",
        vault_id="VAULT-1",
        pdm_file_id=101,
        pdm_file_version=3,
        pdm_synced_at=_SYNCED_AT,
        pdm_sync_state=PdmSyncState.SYNCED,
        pdm_source_item_id=77,
    )
    token = await mint_pat([])

    resp = await client.get(f"/api/v1/pat/made-items/{item.id}", headers={"X-Api-Key": token})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vault_id"] == "VAULT-1"
    assert body["pdm_file_id"] == 101
    assert body["pdm_file_version"] == 3
    assert body["pdm_synced_at"] == "2026-09-03T10:00:00Z"
    assert body["pdm_sync_state"] == "synced"
    assert body["pdm_source_item_id"] == 77


# ── source-item PDM shadow field (divergence for source_item_id is
# checked against pdm_source_item_id, never the web-effective value) ────


async def test_pat_read_made_item_by_part_number_pdm_source_item_id_null_when_unset(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    await _make_item(db, pat_owner.id, part_number="PN-MADE-SRC-NULL", revision="A")
    token = await mint_pat([])

    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-SRC-NULL", headers={"X-Api-Key": token}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["pdm_source_item_id"] is None


async def test_pat_read_made_item_by_part_number_returns_pdm_source_item_id(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    await _make_item(
        db,
        pat_owner.id,
        part_number="PN-MADE-SRC-SET",
        revision="A",
        source_item_id=99,
        pdm_source_item_id=99,
    )
    token = await mint_pat([])

    resp = await client.get(
        "/api/v1/pat/made-items/partnumber/PN-MADE-SRC-SET", headers={"X-Api-Key": token}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["pdm_source_item_id"] == 99


async def test_pat_made_items_list_carries_pdm_source_item_id(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    await _make_item(db, pat_owner.id, part_number="PN-MADE-SRC-LIST-NULL", revision="A")
    await _make_item(
        db,
        pat_owner.id,
        part_number="PN-MADE-SRC-LIST-SET",
        revision="A",
        source_item_id=42,
        pdm_source_item_id=42,
    )
    token = await mint_pat([])

    resp = await client.get("/api/v1/pat/made-items/", headers={"X-Api-Key": token})

    assert resp.status_code == 200, resp.text
    by_part_number = {i["part_number"]: i["pdm_source_item_id"] for i in resp.json()["items"]}
    assert by_part_number["PN-MADE-SRC-LIST-NULL"] is None
    assert by_part_number["PN-MADE-SRC-LIST-SET"] == 42


async def test_pat_read_bought_item_pdm_fields_null_for_web_row(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    supplier = await _supplier(db, pat_owner.id)
    item = await _bought_item(db, pat_owner.id, supplier.id, order_code_1="OC-PDM-NULL")
    token = await mint_pat([])

    resp = await client.get(f"/api/v1/pat/bought-items/{item.id}", headers={"X-Api-Key": token})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vault_id"] is None
    assert body["pdm_file_id"] is None
    assert body["pdm_file_version"] is None
    assert body["pdm_synced_at"] is None
    assert body["pdm_sync_state"] is None


async def test_pat_read_bought_item_returns_pdm_link_fields(
    db: AsyncSession,
    client: httpx.AsyncClient,
    pat_owner: User,
    mint_pat: Callable[[list[str]], Awaitable[str]],
) -> None:
    supplier = await _supplier(db, pat_owner.id)
    item = await _bought_item(
        db,
        pat_owner.id,
        supplier.id,
        order_code_1="OC-PDM-LINK",
        vault_id="VAULT-1",
        pdm_file_id=202,
        pdm_file_version=5,
        pdm_synced_at=_SYNCED_AT,
        pdm_sync_state=PdmSyncState.SYNCED,
    )
    token = await mint_pat([])

    resp = await client.get(f"/api/v1/pat/bought-items/{item.id}", headers={"X-Api-Key": token})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vault_id"] == "VAULT-1"
    assert body["pdm_file_id"] == 202
    assert body["pdm_file_version"] == 5
    assert body["pdm_synced_at"] == "2026-09-03T10:00:00Z"
    assert body["pdm_sync_state"] == "synced"
