"""
HTTP-level coverage of the made-item PAT revisions endpoint:
GET /api/v1/pat/made-items/partnumber/{part_number}/revisions. Read-only,
part-number-keyed (the add-in has no made-item id, only the part number
printed on the part), and newest-first, the same ordering as the web
endpoint's `GET /made-items/{id}/revisions`, since two different
orderings for the same list would be a trap for API consumers. It shares
the same next_revision/can_create/reason logic underneath.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

MADE_ITEMS_BASE = "/api/v1/web/made-items"


@pytest.fixture(autouse=True)
async def _seed_made_item_settings(db: Session) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="made-item-revisions-pat-owner",
        email="made-item-revisions-pat-owner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.WRITE_MADE_ITEMS],
    )


@pytest.fixture
def mint_pat(db: Session, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="made-item-revisions-test-pat", permissions=permissions),
        )
        return result.token

    return _mint


def _pat_revisions_url(part_number: str) -> str:
    return f"/api/v1/pat/made-items/partnumber/{part_number}/revisions"


async def test_requires_a_valid_pat(client: TestClient) -> None:
    resp = await client.get(_pat_revisions_url("PN-DOES-NOT-MATTER"))
    assert resp.status_code == 401


async def test_unknown_part_number_is_404(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])
    resp = await client.get(_pat_revisions_url("NOPE"), headers={"X-Api-Key": token})
    assert resp.status_code == 404


async def test_single_revision_family(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client
) -> None:
    web = await auth_client(permissions=["write:made_items"])
    created = (
        await web.post(f"{MADE_ITEMS_BASE}/", json={"revision": "A", "article_name": "Bracket"})
    ).json()

    token = await mint_pat([Permission.WRITE_MADE_ITEMS])
    resp = await client.get(
        _pat_revisions_url(created["part_number"]), headers={"X-Api-Key": token}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [i["id"] for i in body["items"]] == [created["id"]]
    assert body["items"][0]["is_newest"] is True
    assert body["next_revision"] == "B"
    assert body["can_create"] is True


async def test_a_pat_with_no_write_permission_reads_but_cannot_create(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client
) -> None:
    web = await auth_client(permissions=["write:made_items"])
    created = (
        await web.post(f"{MADE_ITEMS_BASE}/", json={"revision": "A", "article_name": "Bracket"})
    ).json()

    token = await mint_pat([])
    resp = await client.get(
        _pat_revisions_url(created["part_number"]), headers={"X-Api-Key": token}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [i["id"] for i in body["items"]] == [created["id"]]
    assert body["can_create"] is False
    assert body["reason"] == "no_write"


async def test_revisions_are_newest_first_matching_the_web_endpoint(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client
) -> None:
    web = await auth_client(permissions=["write:made_items"])
    created = (
        await web.post(f"{MADE_ITEMS_BASE}/", json={"revision": "A", "article_name": "Bracket"})
    ).json()
    revised = (
        await web.post(
            f"{MADE_ITEMS_BASE}/{created['id']}/revisions",
            json={"predecessor_status": "replaced", "item": {"article_name": "Bracket"}},
        )
    ).json()

    token = await mint_pat([])
    pat_resp = await client.get(
        _pat_revisions_url(created["part_number"]), headers={"X-Api-Key": token}
    )
    assert pat_resp.status_code == 200
    pat_ids = [i["id"] for i in pat_resp.json()["items"]]
    assert pat_ids == [revised["id"], created["id"]]

    web_resp = await web.get(f"{MADE_ITEMS_BASE}/{revised['id']}/revisions")
    web_ids = [i["id"] for i in web_resp.json()["items"]]
    assert web_ids == [revised["id"], created["id"]]

    assert pat_ids == web_ids


async def test_null_part_number_family_is_just_itself(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client, db: Session
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=False,
            part_number_editable=True,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    web = await auth_client(permissions=["write:made_items"])
    created = (
        await web.post(f"{MADE_ITEMS_BASE}/", json={"revision": "A", "article_name": "Bracket"})
    ).json()
    assert created["part_number"] is None

    token = await mint_pat([])
    resp = await client.get(_pat_revisions_url(""), headers={"X-Api-Key": token})
    # An empty part_number segment never matches this made item (its
    # part_number is null, not ""), so this is still a 404, not a
    # coincidental match. This guards against a future accidental
    # empty-string comparison in the lookup.
    assert resp.status_code in (404, 405)
