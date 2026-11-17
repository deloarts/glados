"""
HTTP-level coverage of GET /api/v1/pat/lookups: the add-in's offline
cache bootstrap (one call across suppliers, article groups, fabrication
methods, inspection methods, source item types and source items) and its
weak-ETag 304 short-circuit.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

LOOKUPS_URL = "/api/v1/pat/lookups/"


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="lookups-pat-owner",
        email="lookups-pat-owner@example.com",
        permissions=[Permission.WRITE_PAT],
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
            cmd=CreatePatCommand(name="lookups-test-pat", permissions=permissions),
        )
        return result.token

    return _mint


async def test_requires_a_valid_pat(client: TestClient) -> None:
    resp = await client.get(LOOKUPS_URL)
    assert resp.status_code == 401


async def test_a_pat_with_no_permissions_still_reads(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    """Documents the read-permission contract structurally: none of the
    six list endpoints this replaces gates reads by permission today (a
    valid PAT is the only requirement), so this endpoint's own gate, a
    superset of theirs, is a no-op in practice. There is no permission to
    withhold, so there is nothing to assert a 403 against; an
    empty-permission token still gets 200."""
    token = await mint_pat([])
    resp = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})
    assert resp.status_code == 200


async def test_empty_database_returns_the_full_envelope_shape(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])
    resp = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})

    assert resp.status_code == 200
    body = resp.json()
    assert "server_time" in body
    for key in (
        "suppliers",
        "article_groups",
        "fabrication_methods",
        "inspection_methods",
        "source_item_types",
        "source_items",
    ):
        assert body[key] == []


async def test_response_carries_a_weak_etag(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])
    resp = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})

    etag = resp.headers.get("ETag")
    assert etag is not None
    assert etag.startswith('W/"')
    assert etag.endswith('"')


async def test_repeat_call_with_matching_if_none_match_is_304(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])
    first = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})
    etag = first.headers["ETag"]

    second = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token, "If-None-Match": etag})

    assert second.status_code == 304
    assert second.content == b""


@pytest.mark.parametrize(
    "shape",
    ["strong", "list_with_match_last", "wildcard", "unquoted_weak"],
)
async def test_if_none_match_accepts_every_rfc_7232_shape(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], shape: str
) -> None:
    token = await mint_pat([])
    weak = (await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})).headers["ETag"]
    opaque = weak[len("W/") :]
    header = {
        "strong": opaque,
        "list_with_match_last": f'W/"stale-one", "stale-two", {weak}',
        "wildcard": "*",
        "unquoted_weak": "W/" + opaque.strip('"'),
    }[shape]

    resp = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token, "If-None-Match": header})

    assert resp.status_code == 304
    assert resp.headers["ETag"] == weak


async def test_stale_if_none_match_returns_200_with_a_fresh_etag(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]]
) -> None:
    token = await mint_pat([])
    resp = await client.get(
        LOOKUPS_URL, headers={"X-Api-Key": token, "If-None-Match": 'W/"not-a-real-etag"'}
    )
    assert resp.status_code == 200
    assert resp.headers.get("ETag") is not None


async def test_etag_changes_after_a_mutation(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client
) -> None:
    token = await mint_pat([])
    before = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})
    etag_before = before.headers["ETag"]

    writer = await auth_client(permissions=[Permission.WRITE_SUPPLIERS])
    created = await writer.post("/api/v1/web/suppliers/", json={"name": "Lookup Test Supplier"})
    assert created.status_code == 201

    after_same_etag = await client.get(
        LOOKUPS_URL, headers={"X-Api-Key": token, "If-None-Match": etag_before}
    )
    assert after_same_etag.status_code == 200
    assert after_same_etag.headers["ETag"] != etag_before

    body = after_same_etag.json()
    assert any(s["name"] == "Lookup Test Supplier" for s in body["suppliers"])


async def test_etag_changes_after_an_archive(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client
) -> None:
    """Archiving bumps `changed`, which the ETag's aggregate is keyed on,
    proves a repeat GET after an archive is not silently served from a
    stale 304."""
    writer = await auth_client(
        permissions=[Permission.WRITE_SUPPLIERS, Permission.DELETE_SUPPLIERS]
    )
    created = (
        await writer.post("/api/v1/web/suppliers/", json={"name": "Archive Test Supplier"})
    ).json()

    token = await mint_pat([])
    before = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})
    etag_before = before.headers["ETag"]

    archived = await writer.post(f"/api/v1/web/suppliers/{created['id']}/archive")
    assert archived.status_code == 200

    after = await client.get(
        LOOKUPS_URL, headers={"X-Api-Key": token, "If-None-Match": etag_before}
    )
    assert after.status_code == 200
    assert after.headers["ETag"] != etag_before

    # Archived rows are still part of the offline cache (the add-in needs
    # to know an id it already has locally became archived), so the
    # supplier is still present, just flagged.
    body = after.json()
    match = next(s for s in body["suppliers"] if s["id"] == created["id"])
    assert match["archived"] is True


async def test_customers_carry_only_id_name_and_archived(
    client: TestClient, mint_pat: Callable[[list[str]], Awaitable[str]], auth_client
) -> None:
    writer = await auth_client(permissions=[Permission.WRITE_PROJECTS])
    created = await writer.post(
        "/api/v1/web/customers/", json={"name": "Lookup Customer", "email": "a@example.com"}
    )
    assert created.status_code == 201, created.text

    token = await mint_pat([])
    resp = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})

    assert resp.status_code == 200
    assert resp.json()["customers"] == [
        {"id": created.json()["id"], "name": "Lookup Customer", "archived": False}
    ]


@pytest.mark.parametrize(
    ("path", "key", "permission"),
    [
        ("article-groups", "article_groups", Permission.WRITE_ARTICLE_GROUPS),
        ("fabrication-methods", "fabrication_methods", Permission.WRITE_FABRICATION_METHODS),
        ("inspection-methods", "inspection_methods", Permission.WRITE_INSPECTION_METHODS),
        ("source-item-types", "source_item_types", Permission.WRITE_SOURCE_ITEM_TYPES),
    ],
)
async def test_hand_ordered_families_carry_their_order_and_a_reorder_changes_the_etag(
    client: TestClient,
    mint_pat: Callable[[list[str]], Awaitable[str]],
    auth_client,
    path: str,
    key: str,
    permission: str,
) -> None:
    """A place rewrites only `sort_order`, never `changed`, so the ETag has
    to see the order itself; otherwise the add-in's cache would keep the old
    order behind a 304."""
    writer = await auth_client(permissions=[permission])
    ids = []
    for name in ("Zeta", "Kappa", "Alpha"):
        created = await writer.post(f"/api/v1/web/{path}/", json={"name": {"enGB": name}})
        assert created.status_code in (200, 201), created.text
        ids.append(created.json()["id"])

    token = await mint_pat([])
    before = await client.get(LOOKUPS_URL, headers={"X-Api-Key": token})
    order_before = {row["id"]: row["sort_order"] for row in before.json()[key]}
    assert sorted(ids, key=order_before.__getitem__) == ids

    placed = await writer.post(f"/api/v1/web/{path}/{ids[2]}/place", json={"before_id": ids[0]})
    assert placed.status_code == 204, placed.text

    after = await client.get(
        LOOKUPS_URL, headers={"X-Api-Key": token, "If-None-Match": before.headers["ETag"]}
    )
    assert after.status_code == 200
    assert after.headers["ETag"] != before.headers["ETag"]
    order_after = {row["id"]: row["sort_order"] for row in after.json()[key]}
    assert sorted(ids, key=order_after.__getitem__) == [ids[2], ids[0], ids[1]]


def test_the_openapi_documents_the_payload_and_the_304() -> None:
    """The route answers its own JSONResponse for the ETag, so the payload is
    declared for the contract snapshot instead of being inferred."""
    responses = app.openapi()["paths"][LOOKUPS_URL]["get"]["responses"]

    assert responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LookupsResponse"
    }
    assert "304" in responses
