"""
The /admin/settings/pdm surface end to end: read/write of the connection
settings (no password or token ever leaves the API), the connection probe's
three verdicts, the operation catalogue listing, and the admin API
console's invoke endpoint (read op happy path, the mutating opt-in gate,
the resulting audit entry, an unknown operation id, and permission
checks). The PDM Web API itself is never called, a fake IPdmGateway is
swapped in through app.dependency_overrides the same way
test_api_admin_settings_auth.py fakes the LDAP authenticator.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import get_pdm_gateway_factory
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.errors import PdmUnavailableError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmInvokeResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVersionInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflowState
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.config.settings import cfg

BASE = "/api/v1/web/admin/settings/pdm"

# Real catalogue ids used to exercise the invoke endpoint without needing a
# hand-built spec: one read-only operation whose only path parameter is
# vaultName (server-filled), one mutating operation with exactly one other
# required path parameter.
READ_OP_ID = "get_api_vaultname_workflows"
MUTATING_OP_ID = "put_api_vaultname_folders_parentfolderid"
# Never offered by the console, see application/services/pdm_console_policy.py.
BLOCKED_OP_ID = "put_api_vaultname_configuration_hooks_dll"


class FakeGateway:
    def __init__(self) -> None:
        self.version_result: PdmVersionInfo | Exception = PdmVersionInfo(
            product_name="SOLIDWORKS PDM Professional", app_version="2025", file_version="30.0"
        )
        self.auth_result: PdmAuthResult | Exception = PdmAuthResult(token="tok", user_id=1)
        self.invoke_result: PdmInvokeResult | Exception | None = None
        self.workflows_result: list[PdmWorkflow] | Exception = []
        self.browse_result: list[PdmObjectInfo] | Exception = []

    async def version(self) -> PdmVersionInfo:
        if isinstance(self.version_result, Exception):
            raise self.version_result
        return self.version_result

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        if isinstance(self.auth_result, Exception):
            raise self.auth_result
        return self.auth_result

    async def vault_info(self, token: str) -> object:  # pragma: no cover - unused here
        raise NotImplementedError

    async def search_files(self, token: str, query: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def files_info(self, token: str, file_ids: list[int]) -> object:  # pragma: no cover
        raise NotImplementedError

    async def file_info_from_path(self, token: str, path: str) -> object:  # pragma: no cover
        raise NotImplementedError

    async def browse_folder(self, token: str, folder_id: int) -> list[PdmObjectInfo]:
        if isinstance(self.browse_result, Exception):
            raise self.browse_result
        return self.browse_result

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> object:  # pragma: no cover
        raise NotImplementedError

    async def workflows(self, token: str) -> list[PdmWorkflow]:
        if isinstance(self.workflows_result, Exception):
            raise self.workflows_result
        return self.workflows_result

    async def get_datacard(self, token: str, file_id: int, version: int, folder_id: int) -> object:
        # pragma: no cover: write-back is covered in test_pdm_writeback.py
        raise NotImplementedError

    async def set_datacard_variables(
        self,
        token: str,
        file_id: int,
        folder_id: int,
        configuration_id: int,
        card: object,
        values: dict[str, str],
    ) -> bool:  # pragma: no cover - write-back is covered in test_pdm_writeback.py
        raise NotImplementedError

    async def invoke(
        self,
        token: str | None,
        spec: object,
        path_params: dict[str, object],
        query: dict[str, object],
        body: object | None,
    ) -> PdmInvokeResult:
        if isinstance(self.invoke_result, Exception):
            raise self.invoke_result
        assert self.invoke_result is not None
        return self.invoke_result


@pytest.fixture
def pdm_gateway():
    fake = FakeGateway()
    app.dependency_overrides[get_pdm_gateway_factory] = lambda: lambda connection: fake
    yield fake
    app.dependency_overrides.pop(get_pdm_gateway_factory, None)


@pytest.fixture
async def seeded_pdm(db):
    """A fully configured connection, built on top of conftest's autouse
    bare row so the variable maps keep their real defaults."""
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


def _skipped_snapshot(*, vault_id: str = "V1", file_id: int) -> PdmFileSnapshot:
    """A row parked skipped for a settings reason: the shape
    reset_skipped_to_pending requeues once the admin fixes the setting
    that caused the skip."""
    now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    return PdmFileSnapshot(
        id=0,
        vault_id=vault_id,
        file_id=file_id,
        kind="made",
        name="Bracket.SLDPRT",
        path="\\Made-Parts\\Bracket.SLDPRT",
        parent_folder_id=1,
        version=1,
        state_id=1,
        state="Released",
        modified_at=None,
        first_seen_at=now,
        last_seen_at=now,
        last_ingested_version=None,
        sync_state=PdmFileSyncState.SKIPPED,
        last_error="part number does not match pattern",
        part_number=None,
        revision=None,
        item_id=None,
        parked_payload=None,
    )


def _put_payload(**kwargs) -> dict:
    body = {
        "base_url": "http://pdm-host:65453",
        "vault_name": "MyVault",
        "username": "svc-account",
        "password": "secret",
        "verify_certificate": True,
        "timeout_seconds": 15,
    }
    body.update(kwargs)
    return body


_test_payload = _put_payload


# ── Access control ────────────────────────────────────────────────────


class TestAccessControl:
    async def test_read_requires_authentication(self, client):
        assert (await client.get(BASE)).status_code == 401

    async def test_read_requires_read_settings(self, auth_client):
        assert (await (await auth_client(permissions=[])).get(BASE)).status_code == 403

    async def test_write_requires_write_settings(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        assert (await client.put(BASE, json=_put_payload())).status_code == 403

    async def test_test_connection_requires_write_settings(self, auth_client, pdm_gateway):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        assert (await client.post(f"{BASE}/test", json=_test_payload())).status_code == 403

    async def test_list_operations_requires_read_settings(self, auth_client):
        assert (
            await (await auth_client(permissions=[])).get(f"{BASE}/operations")
        ).status_code == 403

    async def test_invoke_requires_write_settings(self, auth_client, seeded_pdm, pdm_gateway):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.post(
            f"{BASE}/operations/{READ_OP_ID}/invoke",
            json={"path_params": {}, "query": {}, "body": None, "allow_mutating": False},
        )
        assert resp.status_code == 403


# ── Read / write round trip ───────────────────────────────────────────


class TestReadWrite:
    async def test_get_shape_before_configuration(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert body["configured"] is False
        assert body["password_configured"] is False
        assert body["session"]["active"] is False
        assert body["session"]["obtained_at"] is None
        assert "password" not in body
        assert "session_token" not in body
        assert not [k for k in body if "token" in k]

    async def test_get_shape_after_configuration(self, auth_client, seeded_pdm):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert body["configured"] is True
        assert body["password_configured"] is True
        assert body["base_url"] == "http://pdm-host:65453"
        assert body["vault_name"] == "MyVault"
        assert body["username"] == "svc-account"
        assert "password" not in body

    async def test_put_then_get_round_trips_connection_fields(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(vault_name="OtherVault", timeout_seconds=30)

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        assert got["vault_name"] == "OtherVault"
        assert got["timeout_seconds"] == 30
        assert got["password_configured"] is True

    async def test_put_then_get_round_trips_released_and_obsolete_states_per_kind(
        self, auth_client
    ):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(
            made_released_state_ids=[1, 2],
            made_obsolete_state_ids=[3],
            bought_released_state_ids=[4],
            bought_obsolete_state_ids=[5, 6],
        )

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        assert got["made_released_state_ids"] == [1, 2]
        assert got["made_obsolete_state_ids"] == [3]
        assert got["bought_released_state_ids"] == [4]
        assert got["bought_obsolete_state_ids"] == [5, 6]

    async def test_put_then_get_round_trips_replaced_states_per_kind(self, auth_client):
        # Lifecycle status feature (docs/PDM_INTEGRATION.md's "lifecycle
        # mapping" section): a third state-id list per kind, alongside
        # released/obsolete above.
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(
            made_released_state_ids=[1],
            made_obsolete_state_ids=[2],
            made_replaced_state_ids=[3],
            bought_released_state_ids=[4],
            bought_obsolete_state_ids=[5],
            bought_replaced_state_ids=[6, 7],
        )

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        assert got["made_replaced_state_ids"] == [3]
        assert got["bought_replaced_state_ids"] == [6, 7]

    async def test_put_rejects_overlapping_released_and_replaced_state_ids(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(
            BASE,
            json=_put_payload(made_released_state_ids=[1, 2], made_replaced_state_ids=[2]),
        )
        assert resp.status_code == 400

    async def test_put_rejects_overlapping_obsolete_and_replaced_state_ids(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(
            BASE,
            json=_put_payload(bought_obsolete_state_ids=[5], bought_replaced_state_ids=[5]),
        )
        assert resp.status_code == 400

    async def test_put_one_kind_only_leaves_the_other_kind_unchanged(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        await client.put(
            BASE,
            json=_put_payload(
                made_released_state_ids=[1],
                bought_released_state_ids=[2],
            ),
        )

        resp = await client.put(BASE, json={**_put_payload(), "made_released_state_ids": [9]})
        assert resp.status_code == 200

        got = (await client.get(BASE)).json()
        assert got["made_released_state_ids"] == [9]
        assert got["bought_released_state_ids"] == [2]

    async def test_put_then_get_round_trips_watched_folder_folder_id(self, auth_client):
        # folder_id round-trips alongside path, and a
        # folder entered without one still round-trips as None.
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(
            watched_folders=[
                {
                    "path": "\\Made-Parts",
                    "kind": "made",
                    "recursive": True,
                    "enabled": True,
                    "folder_id": 42,
                },
                {
                    "path": "\\Bought-Parts",
                    "kind": "bought",
                    "recursive": True,
                    "enabled": True,
                },
            ]
        )

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        by_path = {f["path"]: f for f in got["watched_folders"]}
        assert by_path["\\Made-Parts"]["folder_id"] == 42
        assert by_path["\\Bought-Parts"]["folder_id"] is None

    async def test_get_includes_label_and_feature_tree_rows_in_item_fields(self, auth_client):
        """Labels and the feature-tree render field are normal mappable,
        addin-owned rows in item_fields (docs/FIELD_OWNERSHIP.md's
        "Label properties and the feature-tree template" section), not a
        separate derived_labels block."""
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        made = {f["field"]: f for f in body["item_fields"]["made"]}
        bought = {f["field"]: f for f in body["item_fields"]["bought"]}

        assert made["article_group_names"]["owner"] == "addin"
        assert made["article_group_names"]["mappable"] is True
        assert made["article_group_names"]["label_of"] == "article_group_ids"
        assert made["process_names"]["label_of"] == "processes"
        assert made["source_item_name"]["label_of"] == "source_item_id"
        assert made["feature_tree_representation"]["owner"] == "addin"
        assert made["feature_tree_representation"]["label_of"] is None
        assert made["article_name"]["label_of"] is None

        assert bought["manufacturer_name"]["owner"] == "addin"
        assert bought["manufacturer_name"]["label_of"] == "manufacturer_id"
        assert bought["article_group_names"]["label_of"] == "article_group_ids"
        assert bought["feature_tree_representation"]["label_of"] is None

        assert body["made_item_variable_map"]["article_group_names"] == "Glados.ArticleGroupNames"
        assert body["made_item_variable_map"]["process_names"] == "Glados.ProcessNames"
        assert body["made_item_variable_map"]["source_item_name"] == "Glados.SourceItemName"
        assert (
            body["made_item_variable_map"]["feature_tree_representation"]
            == "Glados.FeatureTreeRepresentation"
        )
        assert body["bought_item_variable_map"]["manufacturer_name"] == "Glados.ManufacturerName"
        assert body["bought_item_variable_map"]["article_group_names"] == "Glados.ArticleGroupNames"

    async def test_get_includes_default_feature_tree_templates(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert body["made_feature_tree_template"] == (
            '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
        )
        assert body["bought_feature_tree_template"] == (
            '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
        )

    async def test_put_updates_feature_tree_templates(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(
            made_feature_tree_template='$PRP:"Glados.ArticleName"',
            bought_feature_tree_template='$PRP:"Glados.ArticleName" ($PRP:"SW-File Name")',
        )

        resp = await client.put(BASE, json=sent)

        assert resp.status_code == 200
        assert resp.json()["made_feature_tree_template"] == '$PRP:"Glados.ArticleName"'
        assert (
            resp.json()["bought_feature_tree_template"]
            == '$PRP:"Glados.ArticleName" ($PRP:"SW-File Name")'
        )

    async def test_put_rejects_a_multi_line_feature_tree_template(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(
            BASE, json=_put_payload(made_feature_tree_template='$PRP:"A"\n$PRP:"B"')
        )
        assert resp.status_code == 400

    async def test_get_shape_includes_documents_addendum_defaults(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert body["made_item_extensions"] == ["sldprt"]
        assert body["bought_item_extensions"] == ["sldprt", "sldasm"]
        assert body["document_categories"] == {
            "pdf": "drawing",
            "dxf": "dxf",
            "step": "step",
            "stp": "step",
        }
        # thumbnails_enabled deliberately not asserted here, the same SQLite
        # server_default readback caveat as verify_certificate/
        # writeback_enabled, see test_admin_pdm_settings_persistence.py's
        # test_seeded_row_defaults_to_an_unconfigured_connection.

    async def test_put_then_get_round_trips_the_documents_addendum_fields(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(
            made_item_extensions=[".SLDPRT"],
            bought_item_extensions=["SLDASM"],
            document_categories={"PDF": "drawing"},
            thumbnails_enabled=True,
        )

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        assert got["made_item_extensions"] == ["sldprt"]
        assert got["bought_item_extensions"] == ["sldasm"]
        assert got["document_categories"] == {"pdf": "drawing"}
        assert got["thumbnails_enabled"] is True

    async def test_put_rejects_empty_extensions_list(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(BASE, json=_put_payload(made_item_extensions=[]))
        assert resp.status_code == 422

    async def test_put_rejects_unknown_document_category(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(
            BASE, json=_put_payload(document_categories={"pdf": "not-a-category"})
        )
        assert resp.status_code == 422

    async def test_put_with_password_none_keeps_existing_password(self, auth_client, seeded_pdm):
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.put(BASE, json=_put_payload(password=None, vault_name="RenamedVault"))

        assert resp.status_code == 200
        assert resp.json()["password_configured"] is True
        assert resp.json()["vault_name"] == "RenamedVault"

    async def test_put_rejects_bad_base_url_scheme(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(BASE, json=_put_payload(base_url="ftp://pdm-host:65453"))
        assert resp.status_code == 422

    async def test_put_rejects_out_of_range_timeout(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        assert (await client.put(BASE, json=_put_payload(timeout_seconds=0))).status_code == 422

    async def test_get_shape_includes_required_fields_addendum(self, auth_client):
        """docs/reference/pdm-ingest.md section 7: the seeded default requires
        "material" and the fabrication_step pseudo-rule for made items;
        for bought items, whose locked set does not include revision (it
        is data, not identity, for them), the default keeps it required
        anyway. locked_required_fields and required_field_rules are
        always served, read-only."""
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert body["required_fields"] == {
            "made": ["material", "fabrication_step"],
            "bought": ["revision"],
        }
        assert body["locked_required_fields"] == {
            "made": ["part_number", "revision", "article_name"],
            "bought": ["part_number", "article_name", "order_code_1", "manufacturer_id"],
        }
        assert body["required_field_rules"] == {"made": ["fabrication_step"], "bought": []}

    async def test_put_then_get_round_trips_required_fields(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(required_fields={"made": ["material"], "bought": []})

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        assert got["required_fields"] == {"made": ["material"], "bought": []}

    async def test_put_absent_required_fields_keeps_the_stored_selection(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        await client.put(
            BASE, json=_put_payload(required_fields={"made": ["material"], "bought": []})
        )

        resp = await client.put(BASE, json=_put_payload(vault_name="OtherVault"))

        assert resp.status_code == 200
        assert resp.json()["required_fields"] == {"made": ["material"], "bought": []}

    async def test_put_drops_a_locked_name_from_required_fields_silently(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(required_fields={"made": ["part_number", "material"], "bought": []})

        resp = await client.put(BASE, json=sent)

        assert resp.status_code == 200
        assert resp.json()["required_fields"] == {"made": ["material"], "bought": []}

    async def test_put_then_get_round_trips_set_approver_from_pdm(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        sent = _put_payload(set_approver_from_pdm=True)

        assert (await client.put(BASE, json=sent)).status_code == 200
        assert (await client.get(BASE)).json()["set_approver_from_pdm"] is True

    async def test_put_absent_set_approver_from_pdm_keeps_the_stored_value(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        await client.put(BASE, json=_put_payload(set_approver_from_pdm=True))

        resp = await client.put(BASE, json=_put_payload(vault_name="OtherVault"))

        assert resp.status_code == 200
        assert resp.json()["set_approver_from_pdm"] is True

    async def test_changing_connection_clears_the_stored_session(self, auth_client, db):
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
        await repo.save_pdm_session(token="a-real-token", user_id=7, obtained_at=datetime.now(UTC))
        await db.commit()

        client = await auth_client(permissions=Permission.ALL)
        resp = await client.put(BASE, json=_put_payload(vault_name="ADifferentVault"))

        assert resp.status_code == 200
        assert resp.json()["session"]["active"] is False

    async def test_settings_change_is_audited(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        await client.put(BASE, json=_put_payload())

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "pdm"}
        )
        assert audit.status_code == 200
        assert audit.json()["total"] >= 1


_MADE_PARTS_FOLDER = {"path": "\\Made-Parts", "kind": "made", "recursive": True, "enabled": True}


class TestSkippedFilesRequeuedOnSettingsChange:
    """PUT /pdm requeues every `skipped` snapshot row for the poller's
    cached vault_id back to `pending` when a change to the variable maps,
    the released/obsolete state lists or watched_folders makes it worth
    another look. See UpdatePdmSettings and
    IPdmFileSnapshotRepository.reset_skipped_to_pending."""

    async def _seed_vault_and_skipped_files(self, db, count: int = 2) -> None:
        settings_repo = SqlAlchemyAdminSettingsRepository(db)
        await settings_repo.save_pdm_vault_id("V1")
        await db.commit()
        snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await snapshot_repo.upsert_many([_skipped_snapshot(file_id=i) for i in range(1, count + 1)])
        await db.commit()

    async def test_scope_change_requeues_skipped_files_and_is_audited(self, auth_client, db):
        await self._seed_vault_and_skipped_files(db, count=2)
        client = await auth_client(permissions=Permission.ALL)

        # made_released_state_ids is part of the sync scope; changing it
        # makes the reset fire. The seeded rows sit under \Made-Parts, which
        # must stay watched, or the same save marks them missing instead.
        resp = await client.put(
            BASE,
            json={
                **_put_payload(),
                "made_released_state_ids": [77],
                "watched_folders": [_MADE_PARTS_FOLDER],
            },
        )
        assert resp.status_code == 200

        snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
        for file_id in (1, 2):
            row = await snapshot_repo.get_by_file("V1", file_id)
            assert row is not None
            assert row.sync_state == "pending"
            assert row.last_error is None

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "pdm"}
        )
        summaries = " ".join(entry["summary"] for entry in audit.json()["items"])
        assert "2 skipped files queued for re-evaluation" in summaries

    async def test_scope_change_marks_files_outside_every_folder_missing(self, auth_client, db):
        await self._seed_vault_and_skipped_files(db, count=1)
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.put(
            BASE,
            json={
                **_put_payload(),
                "watched_folders": [{**_MADE_PARTS_FOLDER, "path": "\\Other-Parts"}],
            },
        )
        assert resp.status_code == 200

        row = await SqlAlchemyPdmFileSnapshotRepository(db).get_by_file("V1", 1)
        assert row is not None
        assert row.sync_state == "missing"
        assert row.last_error == "file is no longer under a watched folder"

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "pdm"}
        )
        summaries = " ".join(entry["summary"] for entry in audit.json()["items"])
        assert "1 files outside every watched folder marked missing" in summaries

    async def test_unrelated_change_does_not_requeue_skipped_files(self, auth_client, db):
        await self._seed_vault_and_skipped_files(db, count=1)
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.put(BASE, json={**_put_payload(), "timeout_seconds": 30})
        assert resp.status_code == 200

        snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
        row = await snapshot_repo.get_by_file("V1", 1)
        assert row is not None
        assert row.sync_state == "skipped"

    async def test_no_vault_id_yet_does_not_requeue(self, auth_client, db):
        # No save_pdm_vault_id call: vault_id stays "" as seeded.
        snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await snapshot_repo.upsert_many([_skipped_snapshot(vault_id="", file_id=1)])
        await db.commit()
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.put(BASE, json={**_put_payload(), "made_released_state_ids": [77]})
        assert resp.status_code == 200

        row = await snapshot_repo.get_by_file("", 1)
        assert row is not None
        assert row.sync_state == "skipped"


# ── The probe's three verdicts ────────────────────────────────────────


class TestConnectionProbe:
    async def test_successful_probe_is_200(self, auth_client, pdm_gateway):
        pdm_gateway.auth_result = PdmAuthResult(token="tok", user_id=55)
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.post(f"{BASE}/test", json=_test_payload())

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == 55
        assert body["product_name"] == "SOLIDWORKS PDM Professional"

    async def test_rejected_credentials_are_400(self, auth_client, pdm_gateway):
        pdm_gateway.auth_result = PdmAuthenticationFailedError("rejected")
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.post(f"{BASE}/test", json=_test_payload())
        assert resp.status_code == 400

    async def test_unreachable_server_is_503(self, auth_client, pdm_gateway):
        pdm_gateway.version_result = PdmUnavailableError("host unreachable")
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.post(f"{BASE}/test", json=_test_payload())
        assert resp.status_code == 503

    async def test_probing_does_not_persist_the_settings(self, auth_client, pdm_gateway):
        client = await auth_client(permissions=Permission.ALL)
        await client.post(f"{BASE}/test", json=_test_payload(vault_name="ProbedOnly"))

        got = (await client.get(BASE)).json()
        assert got["vault_name"] != "ProbedOnly"


# ── Operation catalogue ──────────────────────────────────────────────


class TestListOperations:
    async def test_lists_the_console_operations_without_vault_name_param(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.get(f"{BASE}/operations")

        assert resp.status_code == 200
        operations = resp.json()
        assert len(operations) == 99  # 113 documented, 14 blocked
        assert BLOCKED_OP_ID not in {op["id"] for op in operations}
        for op in operations:
            assert all(p["name"] != "vaultName" for p in op["params"])


# ── Invoke ────────────────────────────────────────────────────────────


class TestInvokeOperation:
    async def _invoke(self, client, operation_id: str, **kwargs):
        body = {"path_params": {}, "query": {}, "body": None, "allow_mutating": False}
        body.update(kwargs)
        return await client.post(f"{BASE}/operations/{operation_id}/invoke", json=body)

    async def test_read_operation_happy_path(self, auth_client, seeded_pdm, pdm_gateway):
        pdm_gateway.invoke_result = PdmInvokeResult(
            method="GET",
            url="http://pdm-host:65453/api/MyVault/workflows",
            status_code=200,
            elapsed_ms=8,
            content_type="application/json",
            response_json={"Workflows": []},
            response_text=None,
        )
        client = await auth_client(permissions=Permission.ALL)

        resp = await self._invoke(client, READ_OP_ID)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status_code"] == 200
        assert body["response_json"] == {"Workflows": []}
        assert "Authorization" not in body["url"]

    async def test_mutating_operation_is_403_while_the_deployment_leaves_them_off(
        self, auth_client, seeded_pdm, pdm_gateway
    ):
        client = await auth_client(permissions=Permission.ALL)

        resp = await self._invoke(
            client, MUTATING_OP_ID, path_params={"parentFolderId": 5}, allow_mutating=True
        )
        assert resp.status_code == 403

    async def test_mutating_operation_without_allow_mutating_is_400(
        self, auth_client, seeded_pdm, pdm_gateway, monkeypatch
    ):
        monkeypatch.setattr(cfg.pdm, "allow_mutating_operations", True)
        client = await auth_client(permissions=Permission.ALL)

        resp = await self._invoke(client, MUTATING_OP_ID, path_params={"parentFolderId": 5})
        assert resp.status_code == 400

    async def test_mutating_operation_with_allow_mutating_succeeds_and_is_audited(
        self, auth_client, seeded_pdm, pdm_gateway, monkeypatch
    ):
        monkeypatch.setattr(cfg.pdm, "allow_mutating_operations", True)
        pdm_gateway.invoke_result = PdmInvokeResult(
            method="PUT",
            url="http://pdm-host:65453/api/MyVault/folders/5",
            status_code=200,
            elapsed_ms=4,
            content_type="application/json",
            response_json={"Success": True},
            response_text=None,
        )
        client = await auth_client(permissions=Permission.ALL)

        resp = await self._invoke(
            client, MUTATING_OP_ID, path_params={"parentFolderId": 5}, allow_mutating=True
        )
        assert resp.status_code == 200

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "pdm"}
        )
        assert audit.status_code == 200
        assert audit.json()["total"] >= 1
        summaries = " ".join(entry["summary"] for entry in audit.json()["items"])
        assert MUTATING_OP_ID in summaries

    async def test_blocked_operation_is_404_even_in_critical_mode(
        self, auth_client, seeded_pdm, pdm_gateway
    ):
        client = await auth_client(permissions=Permission.ALL)
        resp = await self._invoke(client, BLOCKED_OP_ID, allow_mutating=True)
        assert resp.status_code == 404

    async def test_unknown_operation_id_is_404(self, auth_client, seeded_pdm, pdm_gateway):
        client = await auth_client(permissions=Permission.ALL)
        resp = await self._invoke(client, "does_not_exist")
        assert resp.status_code == 404

    async def test_missing_required_path_param_is_400(self, auth_client, seeded_pdm, pdm_gateway):
        client = await auth_client(permissions=Permission.ALL)
        resp = await self._invoke(client, MUTATING_OP_ID, allow_mutating=True)
        assert resp.status_code == 400

    async def test_vault_name_in_path_params_is_400(self, auth_client, seeded_pdm, pdm_gateway):
        client = await auth_client(permissions=Permission.ALL)
        resp = await self._invoke(client, READ_OP_ID, path_params={"vaultName": "Other"})
        assert resp.status_code == 400

    async def test_invoke_without_configured_connection_is_400(self, auth_client, pdm_gateway):
        """No seeded_pdm here: the autouse bare row has no base_url/vault/
        username/password, so PdmSessionService must refuse before ever
        calling the fake gateway."""
        client = await auth_client(permissions=Permission.ALL)
        resp = await self._invoke(client, READ_OP_ID)
        assert resp.status_code == 400


# ── Workflows / folders proxies, and the poll trigger ──────────────────


@pytest.fixture
async def enabled_pdm(db, seeded_pdm):
    """Builds on seeded_pdm: switches the integration fully on (connection
    configured, one enabled watched folder, one released state) so
    RequestPdmPoll's is_pdm_enabled() gate passes."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=current.made_item_variable_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=True,
            base_url=current.base_url,
            vault_name=current.vault_name,
            username=current.username,
            password=current.password,
            verify_certificate=current.verify_certificate,
            timeout_seconds=current.timeout_seconds,
            session_token=current.session_token,
            session_user_id=current.session_user_id,
            session_obtained_at=current.session_obtained_at,
            watched_folders=[
                PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
            ],
            made_released_state_ids=[5],
            made_obsolete_state_ids=[9],
            made_replaced_state_ids=[9],
            bought_released_state_ids=[5],
            bought_obsolete_state_ids=[9],
            bought_replaced_state_ids=[9],
            poll_interval_minutes=15,
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


class TestGetPdmWorkflows:
    async def test_lists_workflows_and_states(self, auth_client, seeded_pdm, pdm_gateway):
        pdm_gateway.workflows_result = [
            PdmWorkflow(
                workflow_id=1,
                workflow_name="MadeItemWorkflow",
                states=(
                    PdmWorkflowState(state_id=5, state_name="Released"),
                    PdmWorkflowState(state_id=9, state_name="Obsolete"),
                ),
            )
        ]
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        resp = await client.get(f"{BASE}/workflows")

        assert resp.status_code == 200
        body = resp.json()
        assert body == [
            {
                "workflow_id": 1,
                "workflow_name": "MadeItemWorkflow",
                "states": [
                    {"state_id": 5, "state_name": "Released"},
                    {"state_id": 9, "state_name": "Obsolete"},
                ],
            }
        ]

    async def test_requires_read_settings(self, auth_client):
        assert (
            await (await auth_client(permissions=[])).get(f"{BASE}/workflows")
        ).status_code == 403

    async def test_without_configured_connection_is_400(self, auth_client, pdm_gateway):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        assert (await client.get(f"{BASE}/workflows")).status_code == 400


class TestBrowsePdmFolders:
    async def test_lists_folders_only(self, auth_client, seeded_pdm, pdm_gateway):
        def object_info(**overrides: object) -> PdmObjectInfo:
            defaults: dict[str, object] = {
                "id": 1,
                "name": "Made-Parts",
                "size": 0,
                "modified_at": None,
                "version": 0,
                "state": "",
                "state_id": 0,
                "parent_folder_id": 1,
                "path": "Made-Parts",
                "object_type": 0,
                "is_locked": False,
                "locked_by": 0,
                "is_shared": False,
                "is_toolbox": False,
                "is_deleted": False,
            }
            defaults.update(overrides)
            return PdmObjectInfo(**defaults)  # type: ignore[arg-type]

        pdm_gateway.browse_result = [
            object_info(id=1, name="Made-Parts", path="Made-Parts", object_type=0),
            object_info(id=2, name="part.SLDPRT", path="Made-Parts\\part.SLDPRT", object_type=1),
        ]
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        resp = await client.get(f"{BASE}/folders", params={"parent_id": 1})

        assert resp.status_code == 200
        body = resp.json()
        assert body == [{"id": 1, "name": "Made-Parts", "path": "Made-Parts"}]

    async def test_parent_id_defaults_to_vault_root(self, auth_client, seeded_pdm, pdm_gateway):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.get(f"{BASE}/folders")
        assert resp.status_code == 200

    async def test_requires_read_settings(self, auth_client):
        assert (await (await auth_client(permissions=[])).get(f"{BASE}/folders")).status_code == 403


class TestRequestPdmPoll:
    async def test_queues_a_poll_and_clears_last_poll_at(self, auth_client, enabled_pdm, db):
        repo = SqlAlchemyAdminSettingsRepository(db)
        await repo.save_pdm_poll_status(
            at=datetime.now(UTC), error="previous error", summary="previous summary"
        )
        await db.commit()
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.post(f"{BASE}/poll")

        assert resp.status_code == 202
        assert resp.json() == {"accepted": True}
        assert (await repo.get_pdm()).last_poll_at is None

    async def test_is_audited(self, auth_client, enabled_pdm):
        client = await auth_client(permissions=Permission.ALL)
        await client.post(f"{BASE}/poll")

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "pdm"}
        )
        assert audit.status_code == 200
        assert audit.json()["total"] >= 1

    async def test_not_enabled_is_409(self, auth_client, seeded_pdm):
        """seeded_pdm is configured but `enabled` is False."""
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.post(f"{BASE}/poll")
        assert resp.status_code == 409

    async def test_requires_write_settings(self, auth_client, enabled_pdm):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.post(f"{BASE}/poll")
        assert resp.status_code == 403


# ── Reconciliation report ───────────────────────────────────────────────


class TestRequestPdmReconciliation:
    async def test_queues_a_quick_reconciliation(self, auth_client, enabled_pdm, db):
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.post(f"{BASE}/reconcile")

        assert resp.status_code == 202
        assert resp.json() == {"accepted": True}
        repo = SqlAlchemyAdminSettingsRepository(db)
        assert (await repo.get_pdm()).reconcile_requested_deep is False

    async def test_queues_a_deep_reconciliation(self, auth_client, enabled_pdm, db):
        client = await auth_client(permissions=Permission.ALL)

        resp = await client.post(f"{BASE}/reconcile", params={"deep": "true"})

        assert resp.status_code == 202
        repo = SqlAlchemyAdminSettingsRepository(db)
        assert (await repo.get_pdm()).reconcile_requested_deep is True

    async def test_is_audited(self, auth_client, enabled_pdm):
        client = await auth_client(permissions=Permission.ALL)
        await client.post(f"{BASE}/reconcile")

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "pdm"}
        )
        assert audit.status_code == 200
        assert audit.json()["total"] >= 1

    async def test_not_enabled_is_409(self, auth_client, seeded_pdm):
        """seeded_pdm is configured but `enabled` is False."""
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.post(f"{BASE}/reconcile")
        assert resp.status_code == 409

    async def test_requires_write_settings(self, auth_client, enabled_pdm):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.post(f"{BASE}/reconcile")
        assert resp.status_code == 403

    async def test_requires_authentication(self, client):
        assert (await client.post(f"{BASE}/reconcile")).status_code == 401


async def _reconciliation_run(db, *, trigger: PdmSyncTrigger = PdmSyncTrigger.RECONCILIATION):
    from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
        SqlAlchemyPdmSyncRunRepository,
    )
    from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun

    return await SqlAlchemyPdmSyncRunRepository(db).start(
        PdmSyncRun(
            id=0,
            started_at=datetime.now(UTC),
            finished_at=None,
            trigger=trigger,
            files_seen=0,
            changed=0,
            ingested=0,
            skipped=0,
            conflicts=0,
            errors=0,
            missing=0,
            error=None,
            summary="1 orphaned_cad_row",
            folders_walked=0,
        )
    )


async def _reconciliation_finding(db, *, run_id: int, **overrides: object):
    from src.modules.external_data.adapters.outbound.persistence.repositories import (
        pdm_reconciliation_finding_repository as finding_repo_module,
    )
    from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
        PdmReconciliationFinding,
    )

    defaults: dict[str, object] = dict(
        id=0,
        run_id=run_id,
        category=PdmReconciliationCategory.ORPHANED_CAD_ROW,
        severity=PdmReconciliationSeverity.WARNING,
        kind="made",
        item_id=1,
        file_id=100,
        part_number="CAD-1",
        revision="A",
        message="linked PDM file is missing",
        count=1,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    repo = finding_repo_module.SqlAlchemyPdmReconciliationFindingRepository(db)
    await repo.add_many([PdmReconciliationFinding(**defaults)])  # type: ignore[arg-type]
    await db.commit()


class TestGetPdmReconciliation:
    async def test_no_run_yet_returns_null_run_and_empty_counts(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.get(f"{BASE}/reconciliation")
        assert resp.status_code == 200
        assert resp.json() == {"run": None, "counts": {}}

    async def test_returns_the_latest_reconciliation_run_and_counts(self, auth_client, db):
        older = await _reconciliation_run(db)
        newer = await _reconciliation_run(db)
        await _reconciliation_finding(
            db, run_id=older.id, category=PdmReconciliationCategory.REVISION_LAG
        )
        await _reconciliation_finding(
            db, run_id=newer.id, category=PdmReconciliationCategory.ORPHANED_CAD_ROW, count=1
        )
        await _reconciliation_finding(
            db,
            run_id=newer.id,
            file_id=101,
            category=PdmReconciliationCategory.ORPHANED_CAD_ROW,
            count=1,
        )
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        resp = await client.get(f"{BASE}/reconciliation")

        assert resp.status_code == 200
        body = resp.json()
        assert body["run"]["id"] == newer.id
        assert body["run"]["trigger"] == "reconciliation"
        assert body["counts"] == {"orphaned_cad_row": 2}

    async def test_ignores_poll_runs(self, auth_client, db):
        await _reconciliation_run(db, trigger=PdmSyncTrigger.SCHEDULED)
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        resp = await client.get(f"{BASE}/reconciliation")

        assert resp.json()["run"] is None

    async def test_requires_authentication(self, client):
        assert (await client.get(f"{BASE}/reconciliation")).status_code == 401

    async def test_requires_read_settings(self, auth_client):
        client = await auth_client(permissions=[])
        assert (await client.get(f"{BASE}/reconciliation")).status_code == 403


class TestListPdmReconciliationFindings:
    async def test_lists_the_latest_run_s_findings(self, auth_client, db):
        older = await _reconciliation_run(db)
        newer = await _reconciliation_run(db)
        await _reconciliation_finding(db, run_id=older.id, file_id=1)
        await _reconciliation_finding(db, run_id=newer.id, file_id=2)
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        resp = await client.get(f"{BASE}/reconciliation/findings")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["file_id"] == 2

    async def test_filters_by_category_and_kind(self, auth_client, db):
        run = await _reconciliation_run(db)
        await _reconciliation_finding(
            db,
            run_id=run.id,
            file_id=1,
            category=PdmReconciliationCategory.REVISION_LAG,
            kind="made",
        )
        await _reconciliation_finding(
            db,
            run_id=run.id,
            file_id=2,
            category=PdmReconciliationCategory.KIND_MISMATCH,
            kind="bought",
        )
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        resp = await client.get(
            f"{BASE}/reconciliation/findings", params={"category": "kind_mismatch"}
        )

        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["file_id"] == 2

    async def test_no_run_yet_returns_an_empty_page(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.get(f"{BASE}/reconciliation/findings")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0, "skip": 0, "limit": None}

    async def test_requires_authentication(self, client):
        assert (await client.get(f"{BASE}/reconciliation/findings")).status_code == 401

    async def test_requires_read_settings(self, auth_client):
        client = await auth_client(permissions=[])
        assert (await client.get(f"{BASE}/reconciliation/findings")).status_code == 403
