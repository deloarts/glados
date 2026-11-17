"""
Unit tests for ValidatePdmFile: the API-key surface's vault-resolution
wrapper around ValidatePdmPayload (docs/reference/pdm-ingest.md section 8).
No database, no HTTP, no real gateway: ValidatePdmPayload
itself is a fake here (its own rules are covered by
test_validate_pdm_payload.py); these tests only exercise ValidatePdmFile's
own permission check, enabled/configured gate, vault resolution, folder
matching and kind resolution.
"""

from typing import Any

import pytest

from src.modules.external_data.application.dto.pdm_dto import PdmValidationResult
from src.modules.external_data.application.dto.pdm_dto import ValidatePdmPayloadCommand
from src.modules.external_data.application.use_cases.pdm.validate_pdm_file import ValidatePdmFile
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmFileNotFoundError
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories

MADE_FOLDER = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
BY_KIND_FOLDER = PdmWatchedFolder(path="\\Parts", kind="by_kind", recursive=True, enabled=True)
DOCUMENTS_FOLDER = PdmWatchedFolder(
    path="\\Exported Documents", kind="documents", recursive=True, enabled=True
)


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may trigger a PDM sync unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.USE_PDM_ADDIN]
    return factories.make_user(permissions=permissions, **overrides)


def make_pdm_settings(
    *,
    enabled: bool = True,
    vault_id: str = "V1",
    watched_folders: list[PdmWatchedFolder] | None = None,
) -> AdminPdmSettings:
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={"kind": "Glados.Kind"},
        bought_item_variable_map={"kind": "Glados.Kind"},
        enabled=enabled,
        base_url="http://pdm-host:65453",
        vault_name="MyVault",
        username="svc-account",
        password="secret",
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=watched_folders if watched_folders is not None else [MADE_FOLDER],
        made_released_state_ids=[10],
        made_obsolete_state_ids=[20],
        made_replaced_state_ids=[20],
        bought_released_state_ids=[10],
        bought_obsolete_state_ids=[20],
        bought_replaced_state_ids=[20],
        poll_interval_minutes=15,
        vault_id=vault_id,
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )


def make_object(
    *,
    id: int = 100,
    name: str = "part.sldprt",
    path: str = "\\Made-Parts\\part.sldprt",
    version: int = 5,
    state: str = "Released",
    state_id: int = 10,
    parent_folder_id: int = 1,
) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=id,
        name=name,
        size=0,
        modified_at=None,
        version=version,
        state=state,
        state_id=state_id,
        parent_folder_id=parent_folder_id,
        path=path,
        object_type=1,
        is_locked=False,
        locked_by=0,
        is_shared=False,
        is_toolbox=False,
        is_deleted=False,
    )


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm


class FakeGateway:
    def __init__(self) -> None:
        self.by_id: dict[int, PdmObjectInfo] = {}
        self.variables: dict[int, list[PdmConfigVariables]] = {}
        self.variable_error: Exception | None = None
        self.vault_info_result = PdmVaultInfo(
            vault_id="VAULT-GUID",
            version=1,
            vault_type="SolidWorks",
            archive_server="archive",
            database_name="db",
            database_server="dbserver",
        )
        self.vault_info_calls = 0

    async def files_info(self, token: str, file_ids: list[int]) -> list[PdmObjectInfo]:
        return [self.by_id[i] for i in file_ids if i in self.by_id]

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmConfigVariables]:
        if self.variable_error is not None:
            raise self.variable_error
        return self.variables.get(file_id, [])

    async def vault_info(self, token: str) -> PdmVaultInfo:
        self.vault_info_calls += 1
        return self.vault_info_result


class FakeSession:
    def __init__(self, gateway: FakeGateway) -> None:
        self._gateway = gateway

    async def call(self, fn):
        return await fn(self._gateway, "token")


class FakeValidate:
    def __init__(self, result: PdmValidationResult | None = None) -> None:
        self.calls: list[ValidatePdmPayloadCommand] = []
        self._result = result or PdmValidationResult(
            ok=True,
            reasons=[],
            kind="made",
            part_number="CAD-1",
            revision="A",
            would="created",
            file_identity="not_applicable",
            notes=[],
        )

    async def execute(self, cmd: ValidatePdmPayloadCommand) -> PdmValidationResult:
        self.calls.append(cmd)
        return self._result


def make_rig(
    *, pdm_settings: AdminPdmSettings | None = None, gateway: FakeGateway | None = None
) -> tuple[ValidatePdmFile, FakeGateway, FakeValidate, FakeAdminSettingsRepository]:
    gw = gateway or FakeGateway()
    settings_repo = FakeAdminSettingsRepository(pdm_settings or make_pdm_settings())
    validate = FakeValidate()
    use_case = ValidatePdmFile(
        session=FakeSession(gw), admin_settings_repo=settings_repo, validate=validate
    )
    return use_case, gw, validate, settings_repo


class TestPermissionAndEnablement:
    async def test_missing_permission_raises(self):
        use_case, _, _, _ = make_rig()
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_user(permissions=[]), 100)

    async def test_disabled_raises(self):
        use_case, _, _, _ = make_rig(pdm_settings=make_pdm_settings(enabled=False))
        with pytest.raises(PdmNotEnabledError):
            await use_case.execute(make_user(), 100)


class TestFileResolution:
    async def test_file_not_found_raises(self):
        use_case, _, _, _ = make_rig()
        with pytest.raises(PdmFileNotFoundError):
            await use_case.execute(make_user(), 999)

    async def test_private_state_raises_not_found(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(state="", state_id=0)
        use_case, _, validate, _ = make_rig(gateway=gw)
        with pytest.raises(PdmFileNotFoundError):
            await use_case.execute(make_user(), 100)
        assert validate.calls == []

    async def test_unreadable_403_raises_not_found(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object()
        gw.variable_error = PdmApiError("forbidden", status_code=403, body="")
        use_case, _, validate, _ = make_rig(gateway=gw)
        with pytest.raises(PdmFileNotFoundError):
            await use_case.execute(make_user(), 100)
        assert validate.calls == []

    async def test_other_api_error_propagates(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object()
        gw.variable_error = PdmApiError("server error", status_code=500, body="")
        use_case, _, _, _ = make_rig(gateway=gw)
        with pytest.raises(PdmApiError):
            await use_case.execute(make_user(), 100)


class TestFolderMatching:
    async def test_outside_every_folder_returns_unresolved(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Other\\part.sldprt")
        use_case, _, validate, _ = make_rig(gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is False
        assert result.reasons == ["file is outside every watched folder"]
        assert validate.calls == []

    async def test_documents_folder_returns_unresolved(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Exported Documents\\drawing.pdf")
        settings = make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER])
        use_case, _, validate, _ = make_rig(pdm_settings=settings, gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is False
        assert "documents folder" in result.reasons[0]
        assert validate.calls == []


class TestKindResolution:
    async def test_by_kind_folder_reads_the_kind_variable(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Parts\\part.sldprt")
        gw.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "bought"}
            )
        ]
        settings = make_pdm_settings(watched_folders=[BY_KIND_FOLDER])
        use_case, _, validate, _ = make_rig(pdm_settings=settings, gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is True
        assert len(validate.calls) == 1
        assert validate.calls[0].kind == "bought"
        assert validate.calls[0].vault_id == "V1"
        assert validate.calls[0].file_id == 100

    async def test_by_kind_folder_unset_returns_unresolved(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Parts\\part.sldprt")
        gw.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]
        settings = make_pdm_settings(watched_folders=[BY_KIND_FOLDER])
        use_case, _, validate, _ = make_rig(pdm_settings=settings, gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is False
        assert result.reasons == ["kind not set"]
        assert validate.calls == []

    async def test_explicit_folder_disagreeing_variable_is_a_conflict(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Made-Parts\\part.sldprt")
        gw.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "bought"}
            )
        ]
        use_case, _, validate, _ = make_rig(gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is False
        assert "kind variable says bought, folder says made" in result.reasons[0]
        assert validate.calls == []

    async def test_explicit_folder_uses_its_own_kind(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Made-Parts\\part.sldprt", name="part.sldprt")
        gw.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]
        use_case, _, validate, _ = make_rig(gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is True
        assert validate.calls[0].kind == "made"
        assert validate.calls[0].file_name == "part.sldprt"

    async def test_missing_file_level_configuration_is_unresolved(self):
        # Missing file-level configuration is reported the same way any
        # other pre-release unresolvable state is, never handed to
        # ValidatePdmPayload at all.
        gw = FakeGateway()
        gw.by_id[100] = make_object(path="\\Made-Parts\\part.sldprt")
        gw.variables[100] = [
            PdmConfigVariables(
                configuration_name="Default", configuration_id=1, variables={"A": "1"}
            )
        ]
        use_case, _, validate, _ = make_rig(gateway=gw)
        result = await use_case.execute(make_user(), 100)
        assert result.ok is False
        assert result.reasons == ["no file-level datacard configuration"]
        assert validate.calls == []


class TestVaultIdResolution:
    async def test_empty_vault_id_is_fetched_transiently(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object()
        gw.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]
        settings = make_pdm_settings(vault_id="")
        use_case, _, validate, _ = make_rig(pdm_settings=settings, gateway=gw)
        await use_case.execute(make_user(), 100)
        assert gw.vault_info_calls == 1
        assert validate.calls[0].vault_id == "VAULT-GUID"
        # Transient only: never persisted by this read-only use case.
        assert settings.vault_id == ""


class TestBatch:
    async def test_each_file_gets_its_own_outcome_in_request_order(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(id=100)
        gw.by_id[101] = make_object(id=101, state="", state_id=0)
        gw.by_id[102] = make_object(id=102)
        use_case, _, validate, _ = make_rig(gateway=gw)

        outcomes = await use_case.execute_batch(make_user(), [100, 999, 101, 100, 102])

        assert [(o.file_id, o.outcome) for o in outcomes] == [
            (100, "validated"),
            (999, "not_found"),
            (101, "not_found"),
            (102, "validated"),
        ]
        assert outcomes[0].validation is not None
        assert [c.file_id for c in validate.calls] == [100, 102]

    async def test_a_read_error_only_fails_its_own_file(self):
        gw = FakeGateway()
        gw.by_id[100] = make_object(id=100)
        gw.variable_error = PdmApiError("server error", status_code=500, body="")
        use_case, _, _, _ = make_rig(gateway=gw)

        outcomes = await use_case.execute_batch(make_user(), [100])

        assert outcomes[0].outcome == "failed"
        assert outcomes[0].detail

    async def test_files_beyond_the_time_budget_are_not_validated(self, monkeypatch):
        monkeypatch.setattr(
            "src.modules.external_data.application.use_cases.pdm.validate_pdm_file._BATCH_BUDGET_SECONDS",
            -1.0,
        )
        gw = FakeGateway()
        gw.by_id[100] = make_object(id=100)
        use_case, _, validate, _ = make_rig(gateway=gw)

        outcomes = await use_case.execute_batch(make_user(), [100])

        assert outcomes[0].outcome == "not_validated"
        assert validate.calls == []

    async def test_missing_permission_raises(self):
        use_case, _, _, _ = make_rig()
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute_batch(make_user(permissions=[]), [100])
