"""
HTTP-level pagination/sort/search coverage of GET /api/v1/web/users/,
whose query params come from a `UserFilterParams` model like the other
reference tables, with `order_by`, `order_dir` and `search` honoured by
the repository. Follows test_api_customer_crud.py's
`TestList` block as the declared template for the pagination vertical; the
`order_by` allow-list is `id`/`username`/`full_name`/`email`/`created`,
derived from the columns `UserManagementTable.vue` offers as sortable.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import update

from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission


@pytest.fixture
async def lister(auth_client):
    """The full list is user administration, which read:settings opens."""
    return await auth_client(
        username="lister", email="lister@example.com", permissions=[Permission.READ_SETTINGS]
    )


class TestList:
    async def test_lists_everything_created(self, lister, create_user):
        await create_user(username="alpha", email="alpha@example.com")
        await create_user(username="beta", email="beta@example.com")

        body = (await lister.get("/api/v1/web/users/")).json()

        # +1 for the `lister` account itself.
        assert body["total"] == 3
        assert {"alpha", "beta", "lister"} <= {u["username"] for u in body["items"]}

    async def test_limit_caps_the_page_but_not_the_total(self, lister, create_user):
        await create_user(username="alpha", email="alpha@example.com")
        await create_user(username="beta", email="beta@example.com")

        body = (await lister.get("/api/v1/web/users/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, lister, create_user):
        await create_user(username="alpha", email="alpha@example.com")
        await create_user(username="beta", email="beta@example.com")

        first = (await lister.get("/api/v1/web/users/?limit=2")).json()
        second = (await lister.get("/api/v1/web/users/?skip=2&limit=2")).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_filters_by_username(self, lister, create_user):
        await create_user(username="alpha", email="alpha@example.com")
        await create_user(username="beta", email="beta@example.com")

        body = (await lister.get("/api/v1/web/users/?username=alpha")).json()

        assert [u["username"] for u in body["items"]] == ["alpha"]

    async def test_filters_by_is_service_account(self, lister, create_user):
        await create_user(username="alpha", email="alpha@example.com")
        await create_user(username="bot", email="bot@example.com", is_service_account=True)

        excluded = (await lister.get("/api/v1/web/users/?is_service_account=false")).json()
        usernames = {u["username"] for u in excluded["items"]}
        assert "bot" not in usernames
        assert {"alpha", "lister"} <= usernames

        unfiltered = (await lister.get("/api/v1/web/users/")).json()
        assert {"alpha", "bot", "lister"} <= {u["username"] for u in unfiltered["items"]}

    async def test_an_explicit_limit_above_the_max_is_rejected(self, lister):
        response = await lister.get(f"/api/v1/web/users/?limit={MAX_PAGE_SIZE + 1}")
        assert response.status_code == 422

    async def test_a_bare_request_does_not_return_the_whole_table(self, lister, db):
        """Regression guard: a list request with no `limit` must never
        mean "everything", which it would if `UserFilterParams` ever
        bypassed `clamp_page`. Seeded
        directly via the ORM rather than 100+ live requests, mirroring
        test_api_customer_crud.py's own reasoning."""
        row_count = DEFAULT_PAGE_SIZE + 4
        created = datetime.now(UTC)
        db.add_all(
            UserOrmModel(
                username=f"bulk-user-{i}",
                full_name=f"Bulk User {i}",
                email=f"bulk-user-{i}@example.com",
                hashed_password="x",
                created=created,
            )
            for i in range(row_count)
        )
        await db.commit()

        body = (await lister.get("/api/v1/web/users/")).json()

        # +1 for the `lister` account itself.
        assert body["total"] == row_count + 1
        assert len(body["items"]) == DEFAULT_PAGE_SIZE


class TestSortingAndSearch:
    async def test_sorts_by_username_both_directions(self, lister, create_user):
        await create_user(username="zeta", email="zeta@example.com")
        await create_user(username="alpha", email="alpha@example.com")

        asc = (await lister.get("/api/v1/web/users/?order_by=username&order_dir=asc")).json()
        usernames = [u["username"] for u in asc["items"]]
        assert usernames == sorted(usernames)

        desc = (await lister.get("/api/v1/web/users/?order_by=username&order_dir=desc")).json()
        usernames = [u["username"] for u in desc["items"]]
        assert usernames == sorted(usernames, reverse=True)

    async def test_sorts_by_email_both_directions(self, lister, create_user):
        await create_user(username="u1", email="zzz@example.com")
        await create_user(username="u2", email="aaa@example.com")

        asc = (await lister.get("/api/v1/web/users/?order_by=email&order_dir=asc")).json()
        emails = [u["email"] for u in asc["items"]]
        assert emails == sorted(emails)

        desc = (await lister.get("/api/v1/web/users/?order_by=email&order_dir=desc")).json()
        emails = [u["email"] for u in desc["items"]]
        assert emails == sorted(emails, reverse=True)

    async def test_sorts_by_id_both_directions(self, lister, create_user):
        await create_user(username="u1", email="u1@example.com")
        await create_user(username="u2", email="u2@example.com")

        asc = (await lister.get("/api/v1/web/users/?order_by=id&order_dir=asc")).json()
        ids = [u["id"] for u in asc["items"]]
        assert ids == sorted(ids)

        desc = (await lister.get("/api/v1/web/users/?order_by=id&order_dir=desc")).json()
        ids = [u["id"] for u in desc["items"]]
        assert ids == sorted(ids, reverse=True)

    async def test_default_order_is_id_ascending(self, lister, create_user):
        """Without `order_by` the list is ordered by id, oldest first."""
        second = await create_user(username="second", email="second@example.com")

        body = (await lister.get("/api/v1/web/users/")).json()

        ids = [u["id"] for u in body["items"]]
        assert ids == sorted(ids)
        assert second.id in ids

    async def test_sorts_by_full_name_both_directions(self, lister, create_user, db):
        ids = [
            (await create_user(username=f"fn{i}", email=f"fn{i}@example.com")).id for i in range(3)
        ]
        for uid, name in zip(ids, ["Zeta Person", "Alpha Person", "Mike Person"], strict=True):
            await db.execute(
                update(UserOrmModel).where(UserOrmModel.id == uid).values({"full_name": name})
            )
        await db.commit()

        asc = (await lister.get("/api/v1/web/users/?order_by=full_name&order_dir=asc")).json()
        full_names = [u["full_name"] for u in asc["items"]]
        assert full_names == sorted(full_names)

        desc = (await lister.get("/api/v1/web/users/?order_by=full_name&order_dir=desc")).json()
        full_names = [u["full_name"] for u in desc["items"]]
        assert full_names == sorted(full_names, reverse=True)

    async def test_sorts_by_created_both_directions(self, lister, create_user, db):
        ids = [
            (await create_user(username=f"cr{i}", email=f"cr{i}@example.com")).id for i in range(3)
        ]
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for offset, uid in enumerate(ids):
            await db.execute(
                update(UserOrmModel)
                .where(UserOrmModel.id == uid)
                .values({"created": base.replace(day=1 + offset)})
            )
        await db.commit()

        asc = (await lister.get("/api/v1/web/users/?order_by=created&order_dir=asc")).json()
        created = [u["created"] for u in asc["items"]]
        assert created == sorted(created)

        desc = (await lister.get("/api/v1/web/users/?order_by=created&order_dir=desc")).json()
        created = [u["created"] for u in desc["items"]]
        assert created == sorted(created, reverse=True)

    async def test_search_narrows_the_total(self, lister, create_user):
        await create_user(username="deployment-bot", email="bot1@example.com")
        await create_user(username="laptop-alice", email="alice@example.com")
        await create_user(username="deployment-agent", email="bot2@example.com")

        body = (await lister.get("/api/v1/web/users/?search=deployment")).json()

        # `lister` itself doesn't match "deployment".
        assert body["total"] == 2
        assert {u["username"] for u in body["items"]} == {
            "deployment-bot",
            "deployment-agent",
        }
