"""
PDM user mapping end to end: GET /admin/settings/pdm/users (linked,
proposed and service-account rows, including several vault users sharing
one Glados user), POST /admin/settings/pdm/users/link (link, unlink, and
moving a link from one Glados user to another) and the read-only
`pdm_links` field on the user response. The PDM Web API itself is never
called, a fake IPdmGateway is swapped in through app.dependency_overrides
the same way test_api_admin_settings_pdm.py fakes it.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import get_pdm_gateway_factory
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUser
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUserExtended
from src.modules.platform.adapters.outbound.persistence.repositories.user_pdm_link_repository import (
    SqlAlchemyUserPdmLinkRepository,
)
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/pdm/users"
USERS_ME = "/api/v1/web/users/me"


class FakeGateway:
    def __init__(self) -> None:
        self.auth_result: PdmAuthResult = PdmAuthResult(token="tok", user_id=1)
        self.users_result: list[PdmUser] | Exception = []
        self.extended_by_id: dict[int, PdmUserExtended] = {}

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        if isinstance(self.auth_result, Exception):
            raise self.auth_result
        return self.auth_result

    async def list_users(self, token: str) -> list[PdmUser]:
        if isinstance(self.users_result, Exception):
            raise self.users_result
        return self.users_result

    async def user_extended(self, token: str, user_id: int) -> PdmUserExtended:
        return self.extended_by_id[user_id]


@pytest.fixture
def pdm_gateway():
    fake = FakeGateway()
    app.dependency_overrides[get_pdm_gateway_factory] = lambda: lambda connection: fake
    yield fake
    app.dependency_overrides.pop(get_pdm_gateway_factory, None)


@pytest.fixture
async def seeded_pdm(db):
    """A fully configured connection, built on top of conftest's autouse
    bare row so the variable maps keep their real defaults, the same shape
    test_api_admin_settings_pdm.py's own seeded_pdm fixture uses."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=current.made_item_variable_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=False,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
            verify_certificate=True,
            timeout_seconds=15,
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
            watched_folders=current.watched_folders,
            made_released_state_ids=current.made_released_state_ids,
            made_obsolete_state_ids=current.made_obsolete_state_ids,
            made_replaced_state_ids=current.made_obsolete_state_ids,
            bought_released_state_ids=current.bought_released_state_ids,
            bought_obsolete_state_ids=current.bought_obsolete_state_ids,
            bought_replaced_state_ids=current.bought_obsolete_state_ids,
            poll_interval_minutes=current.poll_interval_minutes,
            vault_id=current.vault_id,
            cad_items_read_only=current.cad_items_read_only,
            last_poll_at=current.last_poll_at,
            last_poll_error=current.last_poll_error,
            last_poll_summary=current.last_poll_summary,
            writeback_enabled=current.writeback_enabled,
            made_item_extensions=current.made_item_extensions,
            bought_item_extensions=current.bought_item_extensions,
            document_categories=current.document_categories,
            thumbnails_enabled=current.thumbnails_enabled,
            stuck_after_days=current.stuck_after_days,
            reconcile_requested_deep=current.reconcile_requested_deep,
            required_fields=current.required_fields,
        )
    )
    await db.commit()
    return await repo.get_pdm()


class TestListPdmUsers:
    async def test_lists_linked_proposed_and_service_account_rows(
        self, auth_client, create_user, db, seeded_pdm, pdm_gateway
    ):
        linked = await create_user(username="jdoe", email="jdoe@example.com")
        await SqlAlchemyUserPdmLinkRepository(db).upsert(
            pdm_user_id=2, user_id=linked.id, pdm_username="jdoe"
        )
        await db.commit()
        proposal_candidate = await create_user(username="Alice", email="alice@example.com")

        pdm_gateway.users_result = [
            PdmUser(id=2, username="jdoe", full_name="Jane Doe"),
            PdmUser(id=3, username="alice", full_name="Alice Example"),
            PdmUser(id=4, username="svc-account", full_name="Service Account"),
        ]

        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        resp = await client.get(BASE)

        assert resp.status_code == 200
        rows = {row["pdm_user_id"]: row for row in resp.json()}
        assert rows[2]["linked_user_id"] == linked.id
        assert rows[2]["proposed_user_id"] is None
        assert rows[3]["linked_user_id"] is None
        assert rows[3]["proposed_user_id"] == proposal_candidate.id
        assert rows[4]["is_service_account"] is True
        assert rows[4]["proposed_user_id"] is None

    async def test_several_vault_users_link_to_the_same_glados_user(
        self, auth_client, create_user, db, seeded_pdm, pdm_gateway
    ):
        shared = await create_user(username="jdoe", email="jdoe@example.com")
        link_repo = SqlAlchemyUserPdmLinkRepository(db)
        await link_repo.upsert(pdm_user_id=2, user_id=shared.id, pdm_username="jdoe")
        await link_repo.upsert(pdm_user_id=3, user_id=shared.id, pdm_username="jdoe.alt")
        await db.commit()

        pdm_gateway.users_result = [
            PdmUser(id=2, username="jdoe", full_name="Jane Doe"),
            PdmUser(id=3, username="jdoe.alt", full_name="Jane Doe (alt account)"),
        ]

        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        resp = await client.get(BASE)

        assert resp.status_code == 200
        rows = {row["pdm_user_id"]: row for row in resp.json()}
        assert rows[2]["linked_user_id"] == shared.id
        assert rows[3]["linked_user_id"] == shared.id

    async def test_requires_write_settings(self, auth_client, seeded_pdm, pdm_gateway):
        assert (await (await auth_client(permissions=[])).get(BASE)).status_code == 403

    async def test_without_configured_connection_is_400(self, auth_client, pdm_gateway):
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        assert (await client.get(BASE)).status_code == 400


class TestLinkPdmUsers:
    async def test_links_and_then_unlinks(
        self, auth_client, create_user, db, seeded_pdm, pdm_gateway
    ):
        target = await create_user(username="jdoe", email="jdoe@example.com")
        pdm_gateway.users_result = [PdmUser(id=2, username="jdoe-vault", full_name="Jane Doe")]
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        resp = await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": target.id}]}
        )
        assert resp.status_code == 204
        link_repo = SqlAlchemyUserPdmLinkRepository(db)
        [link] = await link_repo.list_by_user(target.id)
        assert link.pdm_user_id == 2
        assert link.pdm_username == "jdoe-vault"

        resp = await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": None}]}
        )
        assert resp.status_code == 204
        assert await link_repo.list_by_user(target.id) == []

    async def test_relinking_a_pdm_user_moves_it_from_the_previous_holder(
        self, auth_client, create_user, db, seeded_pdm, pdm_gateway
    ):
        old_holder = await create_user(username="old-holder", email="old-holder@example.com")
        new_holder = await create_user(username="new-holder", email="new-holder@example.com")
        pdm_gateway.users_result = [PdmUser(id=2, username="jdoe", full_name="Jane Doe")]
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": old_holder.id}]}
        )

        resp = await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": new_holder.id}]}
        )

        assert resp.status_code == 204
        link_repo = SqlAlchemyUserPdmLinkRepository(db)
        assert await link_repo.list_by_user(old_holder.id) == []
        [link] = await link_repo.list_by_user(new_holder.id)
        assert link.pdm_user_id == 2

    async def test_linking_a_second_pdm_user_to_the_same_glados_user_is_allowed(
        self, auth_client, create_user, db, seeded_pdm, pdm_gateway
    ):
        target = await create_user(username="jdoe", email="jdoe@example.com")
        pdm_gateway.users_result = [
            PdmUser(id=2, username="jdoe", full_name="Jane Doe"),
            PdmUser(id=3, username="jdoe.alt", full_name="Jane Doe (alt)"),
        ]
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": target.id}]}
        )

        resp = await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 3, "user_id": target.id}]}
        )

        assert resp.status_code == 204
        links = {
            link.pdm_user_id: link
            for link in await SqlAlchemyUserPdmLinkRepository(db).list_by_user(target.id)
        }
        assert set(links) == {2, 3}

    async def test_unknown_user_id_is_404(self, auth_client, pdm_gateway):
        # No seeded_pdm: the connection is unconfigured, so the vault
        # username lookup fails open (see LinkPdmUsers' docstring) and the
        # 404 still comes from the user lookup, not a 400 from the vault
        # call.
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        resp = await client.post(
            f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": 999999}]}
        )
        assert resp.status_code == 404

    async def test_requires_write_settings(self, auth_client):
        resp = await (await auth_client(permissions=[])).post(f"{BASE}/link", json={"links": []})
        assert resp.status_code == 403


class TestUserResponsePdmLinks:
    async def test_present_and_empty_by_default(self, auth_client):
        resp = await (await auth_client(permissions=[])).get(USERS_ME)
        assert resp.status_code == 200
        assert resp.json()["pdm_links"] == []

    async def test_not_settable_through_the_user_put_endpoint(self, auth_client):
        client = await auth_client(permissions=[])
        resp = await client.put(USERS_ME, json={"pdm_links": [{"pdm_user_id": 123}]})
        assert resp.status_code == 200
        assert (await client.get(USERS_ME)).json()["pdm_links"] == []

    async def test_reflects_links_after_admin_links_the_account(
        self, auth_client, create_user, db, seeded_pdm, pdm_gateway
    ):
        target = await create_user(username="jdoe", email="jdoe@example.com")
        pdm_gateway.users_result = [PdmUser(id=2, username="jdoe-vault", full_name="Jane Doe")]
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        await admin.post(f"{BASE}/link", json={"links": [{"pdm_user_id": 2, "user_id": target.id}]})

        resp = await admin.get(f"/api/v1/web/users/{target.id}")

        assert resp.status_code == 200
        [link] = resp.json()["pdm_links"]
        assert link["pdm_user_id"] == 2
        assert link["pdm_username"] == "jdoe-vault"
