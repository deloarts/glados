"""
HTTP round trip for inspection checklists: create on a product, the
refusal of other owners for the machinery types, list with the product
relation, update under the edit lock, the
four-eyes release, a new revision that supersedes the released one on its
own release, marking a released revision invalid and the refusal to delete
it. Projects and products are seeded through the real repositories; only
the router under test goes through HTTP.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from tests.integration.conftest import auth_headers

URL = "/api/v1/web/checklists"

ClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]

ITEMS = 3
COMPLETE = {"documentation.circuit": "yes", "documentation.symbols": "na", "pumps.guard": "no"}
REMARKS = {"pumps.guard": "Coupling guard missing"}


async def _product_with_project(db: AsyncSession, creator_id: int) -> tuple[int, int]:
    product = await SqlAlchemyProductRepository(db).save(
        Product(id=0, created=datetime.now(UTC), creator_id=creator_id, product_number="PR-CL-1")
    )
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0,
            created=datetime.now(UTC),
            creator_id=creator_id,
            project_number="P-CL-1",
            product_id=product.id,
        )
    )
    await db.commit()
    return product.id, project.id


def _body(**overrides: Any) -> dict[str, Any]:
    return {
        "type": "hydraulics",
        "title": "Hydraulics checklist, P-CL-1",
        "header": {"designation": "Press 12", "legalBasis": "regulation"},
        "answers": {"documentation.circuit": "yes"},
        "remarks": {},
        "definition_version": 1,
        "item_count": ITEMS,
    } | overrides


@pytest.fixture
async def author(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="cl-author",
        email="cl-author@example.com",
        permissions=[Permission.WRITE_CHECKLISTS, Permission.RELEASE_CHECKLISTS],
    )


@pytest.fixture
async def product_id(db: AsyncSession, author: User) -> int:
    product_id, _ = await _product_with_project(db, author.id)
    return product_id


@pytest.fixture
async def author_client(author: User, client: httpx.AsyncClient) -> httpx.AsyncClient:
    client.headers.update(await auth_headers(author))
    return client


class TestChecklistRoundTrip:
    async def test_checklist_product_lifecycle_with_revisions(
        self,
        product_id: int,
        author_client: httpx.AsyncClient,
        auth_client: ClientFactory,
    ) -> None:
        created = await author_client.post(URL, json=_body(product_id=product_id))
        assert created.status_code == 201, created.text
        first = created.json()
        assert first["product_number"] == "PR-CL-1"
        assert (first["revision"], first["is_latest"], first["verdict"]) == ("0", True, "open")
        assert first["release_required"] is True

        resolved = await author_client.get(f"/api/v1/web/resolve/{first['public_id']}")
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["resource"] == "checklists"

        reader = await auth_client(
            username="cl-reader", email="cl-reader@example.com", permissions=[]
        )
        related = await reader.get(URL, params={"related_product_id": product_id})
        assert related.status_code == 200
        assert [row["id"] for row in related.json()["items"]] == [first["id"]]
        assert "answers" not in related.json()["items"][0]

        lock = await author_client.post(f"{URL}/{first['id']}/lock", json={})
        assert lock.status_code == 200, lock.text
        updated = await author_client.put(
            f"{URL}/{first['id']}",
            json=_body(product_id=product_id, answers=COMPLETE, remarks=REMARKS),
        )
        assert updated.status_code == 200, updated.text
        assert (updated.json()["verdict"], updated.json()["finding_count"]) == ("failed", 1)

        # The author finishes editing, so the releaser is not blocked by the lock.
        assert (await author_client.delete(f"{URL}/{first['id']}/lock")).status_code == 200
        own_release = await author_client.post(f"{URL}/{first['id']}/release")
        assert own_release.status_code == 403
        assert own_release.json()["code"] == "ChecklistOwnReleaseError"

        releaser = await auth_client(
            username="cl-releaser",
            email="cl-releaser@example.com",
            permissions=[Permission.RELEASE_CHECKLISTS],
        )
        released = await releaser.post(f"{URL}/{first['id']}/release")
        assert released.status_code == 200, released.text
        assert released.json()["read_only"] is True
        assert released.json()["finished"] is True

        edit_released = await author_client.put(
            f"{URL}/{first['id']}", json=_body(product_id=product_id, answers=COMPLETE)
        )
        assert edit_released.status_code == 409

        revised = await author_client.post(
            f"{URL}/{first['id']}/revise", json={"reason": "Pump replaced"}
        )
        assert revised.status_code == 201, revised.text
        second = revised.json()
        assert (second["revision"], second["revision_reason"]) == ("1", "Pump replaced")
        assert second["answers"] == COMPLETE

        latest = await reader.get(URL, params={"product_id": product_id})
        assert [row["id"] for row in latest.json()["items"]] == [second["id"]]
        history = await reader.get(f"{URL}/{second['id']}/revisions")
        assert [row["revision"] for row in history.json()] == ["1", "0"]
        assert history.json()[1]["superseded_at"] is None

        second_release = await releaser.post(f"{URL}/{second['id']}/release")
        assert second_release.status_code == 200, second_release.text
        previous = await reader.get(f"{URL}/{first['id']}")
        assert previous.json()["superseded_at"] is not None

        manager = await auth_client(
            username="cl-manager",
            email="cl-manager@example.com",
            permissions=[Permission.WRITE_CHECKLISTS, Permission.MANAGE_CHECKLISTS],
        )
        invalid = await manager.post(
            f"{URL}/{second['id']}/mark-invalid", json={"reason": "Pressure test skipped"}
        )
        assert invalid.status_code == 200, invalid.text
        assert invalid.json()["released_at"] is not None
        assert invalid.json()["invalid_reason"] == "Pressure test skipped"
        # Marking invalid does not bring the superseded revision back.
        previous = await reader.get(f"{URL}/{first['id']}")
        assert previous.json()["superseded_at"] is not None

        # A released revision is kept, also once it is marked invalid.
        kept = await manager.delete(f"{URL}/{second['id']}")
        assert kept.status_code == 409
        assert kept.json()["code"] == "ReleasedDocumentDeleteError"

    async def test_checklist_release_needs_remarks_on_findings(
        self, product_id: int, author_client: httpx.AsyncClient, auth_client: ClientFactory
    ) -> None:
        created = await author_client.post(URL, json=_body(product_id=product_id, answers=COMPLETE))
        assert created.status_code == 201, created.text
        releaser = await auth_client(
            username="cl-releaser2",
            email="cl-releaser2@example.com",
            permissions=[Permission.RELEASE_CHECKLISTS, Permission.MANAGE_CHECKLISTS],
        )
        refused = await releaser.post(f"{URL}/{created.json()['id']}/release")
        assert refused.status_code == 409
        assert refused.json()["code"] == "ChecklistIncompleteError"

    async def test_checklist_list_sort(
        self, product_id: int, author_client: httpx.AsyncClient
    ) -> None:
        for title, kind in (("beta", "pneumatics"), ("Alpha", "hydraulics"), ("gamma", "robotics")):
            created = await author_client.post(
                URL, json=_body(type=kind, title=title, product_id=product_id)
            )
            assert created.status_code == 201, created.text

        async def titles(**params: object) -> list[str]:
            resp = await author_client.get(URL, params=params)
            assert resp.status_code == 200, resp.text
            return [row["title"] for row in resp.json()["items"]]

        assert await titles() == ["gamma", "Alpha", "beta"]
        assert await titles(order_by="title") == ["Alpha", "beta", "gamma"]
        assert await titles(order_by="title", order_dir="desc") == ["gamma", "beta", "Alpha"]
        assert await titles(order_by="type") == ["Alpha", "beta", "gamma"]
        assert await titles(order_by="created", order_dir="asc") == ["beta", "Alpha", "gamma"]
        assert (await author_client.get(URL, params={"order_dir": "up"})).status_code == 422

    async def test_checklist_list_rows_name_the_machine(
        self, product_id: int, author_client: httpx.AsyncClient
    ) -> None:
        created = await author_client.post(URL, json=_body(product_id=product_id))
        assert created.status_code == 201, created.text

        rows = (await author_client.get(URL)).json()["items"]
        assert [row["designation"] for row in rows] == [created.json()["header"].get("designation")]

    async def test_checklist_machinery_types_refuse_other_owners(
        self, db: AsyncSession, author: User, author_client: httpx.AsyncClient
    ) -> None:
        project = await SqlAlchemyProjectRepository(db).save(
            Project(id=0, created=datetime.now(UTC), creator_id=author.id, project_number="P-CL-2")
        )
        await db.commit()
        for owner in ({}, {"project_id": project.id}):
            refused = await author_client.post(URL, json=_body(**owner))
            assert refused.status_code == 422, refused.text
            assert refused.json()["code"] == "ChecklistOwnerNotAllowedError"

    async def test_checklist_rejects_bad_payloads(
        self, product_id: int, author_client: httpx.AsyncClient
    ) -> None:
        def body(**overrides: Any) -> dict[str, Any]:
            return _body(product_id=product_id, **overrides)

        unknown_type = await author_client.post(URL, json=body(type="welding"))
        assert unknown_type.status_code == 422
        bad_answer = await author_client.post(
            URL, json=body(answers={"documentation.circuit": "maybe"})
        )
        assert bad_answer.status_code == 422
        bad_key = await author_client.post(URL, json=body(answers={"no-dot": "yes"}))
        assert bad_key.status_code == 422
        too_many = await author_client.post(URL, json=body(item_count=1, answers=COMPLETE))
        assert too_many.status_code == 422
