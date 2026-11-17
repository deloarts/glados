"""
HTTP round trip for saved calculations: create on a project, a product or
personally, list and read with the visibility rules, update under the edit
lock, release, mark a released revision invalid, and the refusal to delete
a released revision. Projects and products are seeded through the real
repositories; only the router under test goes through HTTP.
"""

import re
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

URL = "/api/v1/web/calculations"

ClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


async def _project(db: AsyncSession, creator_id: int, number: str = "P-CALC-1") -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=number)
    )
    await db.commit()
    return project.id


async def _product(db: AsyncSession, creator_id: int, number: str = "PR-CALC-1") -> int:
    product = await SqlAlchemyProductRepository(db).save(
        Product(id=0, created=datetime.now(UTC), creator_id=creator_id, product_number=number)
    )
    await db.commit()
    return product.id


def _body(**overrides: Any) -> dict[str, Any]:
    return {
        "tool": "fit_calculator",
        "title": "Bearing seat Ø25",
        "inputs": {"d": 25, "hole": "H7", "shaft": "g6"},
        "results": {"fitType": "clearance", "maxClearance": 0.041},
        "input_version": 1,
        "engine_version": 1,
    } | overrides


@pytest.fixture
async def author(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="calc-author",
        email="calc-author@example.com",
        permissions=[Permission.WRITE_CALCULATIONS, Permission.RELEASE_CALCULATIONS],
    )


@pytest.fixture
async def author_client(author: User, client: httpx.AsyncClient) -> httpx.AsyncClient:
    client.headers.update(await auth_headers(author))
    return client


class TestCalculationRoundTrip:
    async def test_calculation_project_lifecycle(
        self,
        db: AsyncSession,
        author: User,
        author_client: httpx.AsyncClient,
        auth_client: ClientFactory,
    ) -> None:
        project_id = await _project(db, author.id)

        created = await author_client.post(URL, json=_body(project_id=project_id))
        assert created.status_code == 201, created.text
        calc = created.json()
        assert calc["project_number"] == "P-CALC-1"

        by_public_id = await author_client.get(f"{URL}/by-public-id/{calc['public_id']}")
        assert by_public_id.status_code == 200
        assert by_public_id.json()["id"] == calc["id"]

        resolved = await author_client.get(f"/api/v1/web/resolve/{calc['public_id']}")
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["resource"] == "calculations"
        assert resolved.json()["id"] == calc["id"]
        assert calc["creator_full_name"]
        assert calc["inputs"]["hole"] == "H7"

        reader = await auth_client(
            username="calc-reader", email="calc-reader@example.com", permissions=[]
        )
        listed = await reader.get(URL, params={"project_id": project_id})
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()["items"]] == [calc["id"]]
        assert "inputs" not in listed.json()["items"][0]

        body = _body(title="Bearing seat Ø30", inputs={"d": 30}, project_id=project_id)
        unlocked = await author_client.put(f"{URL}/{calc['id']}", json=body)
        assert unlocked.status_code == 409
        assert unlocked.json()["code"] == "DocumentNotLockedError"
        lock = await author_client.post(f"{URL}/{calc['id']}/lock", json={})
        assert lock.status_code == 200, lock.text
        updated = await author_client.put(f"{URL}/{calc['id']}", json=body)
        assert updated.status_code == 200, updated.text
        assert updated.json()["title"] == "Bearing seat Ø30"

        released = await author_client.post(f"{URL}/{calc['id']}/release")
        assert released.status_code == 200, released.text
        assert released.json()["released_by_full_name"] == calc["creator_full_name"]

        locked = await author_client.put(f"{URL}/{calc['id']}", json=_body(project_id=project_id))
        assert locked.status_code == 409
        assert locked.json()["code"] == "CalculationReleasedError"

        not_allowed = await author_client.delete(f"{URL}/{calc['id']}")
        assert not_allowed.status_code == 409
        assert not_allowed.json()["code"] == "ReleasedDocumentDeleteError"

        manager = await auth_client(
            username="calc-manager",
            email="calc-manager@example.com",
            permissions=[Permission.WRITE_CALCULATIONS, Permission.MANAGE_CALCULATIONS],
        )
        not_manager = await author_client.post(
            f"{URL}/{calc['id']}/mark-invalid", json={"reason": "Wrong load"}
        )
        assert not_manager.status_code == 403
        invalid = await manager.post(
            f"{URL}/{calc['id']}/mark-invalid", json={"reason": "Wrong load"}
        )
        assert invalid.status_code == 200, invalid.text
        # The release stays on record; the revision is only marked invalid.
        assert invalid.json()["released_at"] is not None
        assert invalid.json()["invalid_reason"] == "Wrong load"
        assert invalid.json()["invalid_by_id"] is not None
        assert invalid.json()["invalid_by_full_name"]
        twice = await manager.post(f"{URL}/{calc['id']}/mark-invalid", json={"reason": "again"})
        assert twice.status_code == 409
        assert twice.json()["code"] == "DocumentAlreadyInvalidError"

        # Released revisions are kept, also for managers and once invalid.
        kept = await manager.delete(f"{URL}/{calc['id']}")
        assert kept.status_code == 409
        assert (await author_client.get(f"{URL}/{calc['id']}")).status_code == 200

    async def test_calculation_personal_hidden_from_other_users(
        self, author_client: httpx.AsyncClient, auth_client: ClientFactory
    ) -> None:
        created = await author_client.post(URL, json=_body())
        assert created.status_code == 201, created.text
        calc_id = created.json()["id"]

        mine = await author_client.get(URL, params={"personal_only": True, "mine": True})
        assert [row["id"] for row in mine.json()["items"]] == [calc_id]

        other = await auth_client(
            username="calc-other",
            email="calc-other@example.com",
            permissions=[Permission.WRITE_CALCULATIONS],
        )
        assert (await other.get(f"{URL}/{calc_id}")).status_code == 404
        assert (await other.get(URL)).json()["total"] == 0

    async def test_calculation_list_search_and_pagination(
        self, author_client: httpx.AsyncClient
    ) -> None:
        for title in ("Lift axis A", "Lift axis B", "Gantry 100%"):
            created = await author_client.post(URL, json=_body(tool="drive_sizing", title=title))
            assert created.status_code == 201, created.text

        found = await author_client.get(URL, params={"tool": "drive_sizing", "search": "lift"})
        assert sorted(row["title"] for row in found.json()["items"]) == [
            "Lift axis A",
            "Lift axis B",
        ]

        # A percent sign is a literal character, not a wildcard.
        literal = await author_client.get(URL, params={"search": "100%"})
        assert [row["title"] for row in literal.json()["items"]] == ["Gantry 100%"]

        page = await author_client.get(URL, params={"tool": "drive_sizing", "limit": 2, "skip": 2})
        assert page.json()["total"] == 3
        assert len(page.json()["items"]) == 1

    async def test_calculation_list_sort(self, author_client: httpx.AsyncClient) -> None:
        for title, tool in (
            ("beta", "safety_distance"),
            ("Alpha", "drive_sizing"),
            ("gamma", "drive_sizing"),
        ):
            created = await author_client.post(URL, json=_body(tool=tool, title=title))
            assert created.status_code == 201, created.text
        released = (await author_client.get(URL, params={"search": "gamma"})).json()["items"][0]
        await author_client.post(f"{URL}/{released['id']}/release")

        async def titles(**params: object) -> list[str]:
            resp = await author_client.get(URL, params=params)
            assert resp.status_code == 200, resp.text
            return [row["title"] for row in resp.json()["items"]]

        # Without a sort the most recently changed come first: the release changed gamma.
        assert await titles() == ["gamma", "Alpha", "beta"]
        # Titles sort without regard to case.
        assert await titles(order_by="title") == ["Alpha", "beta", "gamma"]
        assert await titles(order_by="title", order_dir="desc") == ["gamma", "beta", "Alpha"]
        assert (await titles(order_by="tool", order_dir="desc"))[:1] == ["beta"]
        # Drafts have no release time and come after the released ones.
        assert (await titles(order_by="released"))[0] == "gamma"
        assert (await titles(order_by="released", order_dir="desc"))[0] == "gamma"
        assert (await author_client.get(URL, params={"order_by": "creator"})).status_code == 422

    async def test_calculation_list_owner_and_status_filters(
        self, db: AsyncSession, author: User, author_client: httpx.AsyncClient
    ) -> None:
        project_id = await _project(db, author.id, number="P-CALC-F")
        product_id = await _product(db, author.id, number="PR-CALC-F")
        personal = (await author_client.post(URL, json=_body(title="Personal"))).json()
        on_project = (
            await author_client.post(URL, json=_body(title="On project", project_id=project_id))
        ).json()
        await author_client.post(URL, json=_body(title="On product", product_id=product_id))
        await author_client.post(f"{URL}/{on_project['id']}/release")

        async def titles(**params: object) -> list[str]:
            resp = await author_client.get(URL, params=params)
            assert resp.status_code == 200, resp.text
            return sorted(row["title"] for row in resp.json()["items"])

        assert await titles(owner="personal") == [personal["title"]]
        assert await titles(owner="project") == ["On project"]
        assert await titles(owner="product") == ["On product"]
        assert await titles(released=True) == ["On project"]
        assert await titles(released=False) == ["On product", "Personal"]
        assert await titles(project_id=project_id, released=True) == ["On project"]

    async def test_calculation_product_owner(
        self, db: AsyncSession, author: User, author_client: httpx.AsyncClient
    ) -> None:
        product_id = await _product(db, author.id)
        created = await author_client.post(URL, json=_body(product_id=product_id))
        assert created.status_code == 201, created.text
        assert created.json()["product_number"] == "PR-CALC-1"

        listed = await author_client.get(URL, params={"product_id": product_id})
        assert listed.json()["total"] == 1

    async def test_calculation_list_related_product(
        self, db: AsyncSession, author: User, author_client: httpx.AsyncClient
    ) -> None:
        product_id = await _product(db, author.id, number="PR-CALC-R")
        built = await SqlAlchemyProjectRepository(db).save(
            Project(
                id=0,
                created=datetime.now(UTC),
                creator_id=author.id,
                project_number="P-CALC-R1",
                product_id=product_id,
            )
        )
        await db.commit()
        other_project_id = await _project(db, author.id, number="P-CALC-R2")
        await author_client.post(URL, json=_body(title="On product", product_id=product_id))
        await author_client.post(URL, json=_body(title="On its project", project_id=built.id))
        await author_client.post(URL, json=_body(title="Elsewhere", project_id=other_project_id))
        await author_client.post(URL, json=_body(title="Personal"))

        resp = await author_client.get(URL, params={"related_product_id": product_id})
        assert resp.status_code == 200, resp.text
        assert sorted(row["title"] for row in resp.json()["items"]) == [
            "On its project",
            "On product",
        ]


class TestCalculationValidation:
    async def test_calculation_both_owners_rejected(
        self, db: AsyncSession, author: User, author_client: httpx.AsyncClient
    ) -> None:
        project_id = await _project(db, author.id, number="P-CALC-2")
        product_id = await _product(db, author.id, number="PR-CALC-2")
        resp = await author_client.post(
            URL, json=_body(project_id=project_id, product_id=product_id)
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "CalculationOwnerConflictError"

    async def test_calculation_payload_too_large_rejected(
        self, author_client: httpx.AsyncClient
    ) -> None:
        resp = await author_client.post(URL, json=_body(inputs={"blob": "x" * 300_000}))
        assert resp.status_code == 422

    async def test_calculation_create_needs_permission(self, auth_client: ClientFactory) -> None:
        reader = await auth_client(
            username="calc-nowrite", email="calc-nowrite@example.com", permissions=[]
        )
        resp = await reader.post(URL, json=_body())
        assert resp.status_code == 403


class TestCalculationRevisions:
    async def test_calculation_revision_continues_the_document(
        self, db: AsyncSession, author: User, author_client: httpx.AsyncClient
    ) -> None:
        project_id = await _project(db, author.id, number="P-CALC-REV")
        calc = (await author_client.post(URL, json=_body(project_id=project_id))).json()
        # The seeded made item settings start at revision "0".
        assert calc["revision"] == "0"
        assert calc["is_latest"] is True
        assert calc["locked_by_id"] is None

        draft_revision = await author_client.post(
            f"{URL}/{calc['id']}/revise", json={"reason": "x"}
        )
        assert draft_revision.status_code == 409
        assert draft_revision.json()["code"] == "CalculationNotReleasedError"

        await author_client.post(f"{URL}/{calc['id']}/release")
        revised = await author_client.post(
            f"{URL}/{calc['id']}/revise", json={"reason": "New gearbox"}
        )
        assert revised.status_code == 201, revised.text
        revision = revised.json()
        assert revision["revision"] == "1"
        assert revision["lineage"] == calc["lineage"]
        # One document number for every revision, from the default format.
        assert re.fullmatch(r"CAL-\d{2}-\d{4}", calc["document_number"])
        assert revision["document_number"] == calc["document_number"]
        assert revision["public_id"] != calc["public_id"]
        assert revision["released_at"] is None

        listed = await author_client.get(URL, params={"project_id": project_id})
        assert [row["id"] for row in listed.json()["items"]] == [revision["id"]]
        everything = await author_client.get(
            URL, params={"project_id": project_id, "all_revisions": True}
        )
        assert {row["id"] for row in everything.json()["items"]} == {calc["id"], revision["id"]}

        revisions = await author_client.get(f"{URL}/{calc['id']}/revisions")
        assert [(r["revision"], r["is_latest"]) for r in revisions.json()] == [
            ("1", True),
            ("0", False),
        ]

        old = await author_client.put(f"{URL}/{calc['id']}", json=_body(project_id=project_id))
        assert old.status_code == 409
        assert old.json()["code"] == "CalculationReleasedError"
