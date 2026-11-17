"""
HTTP-level coverage of made-item revision endpoints:
GET/POST /api/v1/web/made-items/{id}/revisions.
"""

from datetime import UTC
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.article_group_repository import (
    SqlAlchemyArticleGroupRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.platform.domain.value_objects.localized_text import LocalizedText

MADE_ITEMS_BASE = "/api/v1/web/made-items"


def _settings(**overrides: object) -> AdminMadeItemSettings:
    defaults: dict = dict(
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
    defaults.update(overrides)
    return AdminMadeItemSettings(**defaults)


@pytest.fixture(autouse=True)
async def _seed_made_item_settings(db: Session) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(_settings())
    await db.commit()


async def _create(client: TestClient, **overrides: object) -> dict:
    body = {"revision": "A", "article_name": "Bracket"} | overrides
    resp = await client.post(f"{MADE_ITEMS_BASE}/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_revisions(client: TestClient, item_id: int) -> dict:
    resp = await client.get(f"{MADE_ITEMS_BASE}/{item_id}/revisions")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_revision(client: TestClient, item_id: int, **overrides: object):
    body = {
        "predecessor_status": overrides.pop("predecessor_status", "replaced"),
        "item": {"article_name": "Bracket"} | overrides,
    }
    return await client.post(f"{MADE_ITEMS_BASE}/{item_id}/revisions", json=body)


async def test_get_revisions_requires_no_special_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:made_items"]
    )
    created = await _create(creator)
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )
    body = await _get_revisions(reader, created["id"])
    assert [i["id"] for i in body["items"]] == [created["id"]]
    assert body["reason"] == "no_write"
    assert body["can_create"] is False


async def test_get_revisions_single_item_family(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    body = await _get_revisions(client, created["id"])
    assert len(body["items"]) == 1
    assert body["items"][0]["is_newest"] is True
    assert body["next_revision"] == "B"
    assert body["can_create"] is True
    assert body["reason"] is None


async def test_post_revision_happy_path(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)

    resp = await _create_revision(client, created["id"], predecessor_status="replaced")
    assert resp.status_code == 201, resp.text
    new_item = resp.json()

    assert new_item["revision"] == "B"
    assert new_item["part_number"] == created["part_number"]
    assert new_item["status"] == "active"
    assert new_item["data_source"] == "WEB"
    assert new_item["successor_item_id"] is None
    # files are not part of MadeItemResponse at all (separate sub-resource);
    # "not copied" is covered at the unit level (create_made_item_revision).

    predecessor = (await client.get(f"{MADE_ITEMS_BASE}/{created['id']}")).json()
    assert predecessor["status"] == "replaced"
    assert predecessor["successor_item_id"] == new_item["id"]

    revisions = await _get_revisions(client, new_item["id"])
    assert [i["id"] for i in revisions["items"]] == [new_item["id"], created["id"]]
    assert revisions["next_revision"] == "C"


@pytest.mark.parametrize("predecessor_status", ["inactive", "active"])
async def test_post_revision_predecessor_status_without_successor_link(
    auth_client, predecessor_status: str
) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)

    resp = await _create_revision(client, created["id"], predecessor_status=predecessor_status)
    assert resp.status_code == 201, resp.text

    predecessor = (await client.get(f"{MADE_ITEMS_BASE}/{created['id']}")).json()
    assert predecessor["status"] == predecessor_status
    assert predecessor["successor_item_id"] is None


async def test_post_revision_requires_write_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:made_items"]
    )
    created = await _create(creator)
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )
    resp = await _create_revision(reader, created["id"])
    assert resp.status_code == 403


async def test_post_revision_on_cad_item_rejected(auth_client, db: Session) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    # Only PDM ingest makes a CAD row, so the test flips the stored flag.
    await db.execute(
        update(MadeItemOrmModel)
        .where(MadeItemOrmModel.id == created["id"])
        .values(data_source="CAD")
    )
    await db.commit()

    resp = await _create_revision(client, created["id"])
    assert resp.status_code == 409
    assert resp.json()["code"] == "MadeItemRevisionManagedByPdmError"


async def test_post_revision_on_non_newest_row_rejected(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    first_revision = (await _create_revision(client, created["id"])).json()
    assert first_revision["revision"] == "B"

    # created["id"] is now the predecessor ("replaced"), no longer the
    # family's newest row.
    resp = await _create_revision(client, created["id"])
    assert resp.status_code == 409
    assert resp.json()["code"] == "MadeItemNotNewestRevisionError"


async def test_post_revision_unparseable_current_revision_rejected(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client, revision="A.1")

    resp = await _create_revision(client, created["id"])
    assert resp.status_code == 409
    assert resp.json()["code"] == "RevisionNotIncrementableError"


async def test_post_revision_copies_processes_and_article_groups(auth_client, db: Session) -> None:
    group = await SqlAlchemyArticleGroupRepository(db).save(
        ArticleGroup(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Fasteners"}),
            label_color="#999999",
            label_font_color="#000000",
            description=LocalizedText(),
            creator_id=1,
        )
    )

    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client, article_group_ids=[group.id])

    resp = await _create_revision(client, created["id"], article_group_ids=[group.id])
    assert resp.status_code == 201, resp.text
    new_item = resp.json()
    assert [g["id"] for g in new_item["article_groups"]] == [group.id]


async def test_null_part_number_revision_family_is_just_itself(auth_client, db: Session) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(
        _settings(part_number_auto=False, part_number_editable=True)
    )
    await db.commit()
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    assert created["part_number"] is None

    revisions = await _get_revisions(client, created["id"])
    assert [i["id"] for i in revisions["items"]] == [created["id"]]

    resp = await _create_revision(client, created["id"])
    assert resp.status_code == 201, resp.text
    assert resp.json()["part_number"] is None
    assert resp.json()["revision"] == "B"
