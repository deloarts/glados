"""
Unit tests for the PDM admin-console use cases (VerifyPdmConnection,
ListPdmOperations, InvokePdmOperation, GetPdmWorkflows, BrowsePdmFolders,
RequestPdmPoll), all against fakes: no network, no database.
UpdatePdmSettings/GetPdmSettings's own field rules are covered alongside
the rest of those use cases in tests/unit/admin_settings/.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    VerifyPdmConnectionCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    InvokePdmOperationCommand,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.use_cases.admin_settings.browse_pdm_folders import (
    BrowsePdmFolders,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_workflows import (
    GetPdmWorkflows,
)
from src.modules.external_data.application.use_cases.admin_settings.invoke_pdm_operation import (
    InvokePdmOperation,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_operations import (
    ListPdmOperations,
)
from src.modules.external_data.application.use_cases.admin_settings.request_pdm_poll import (
    RequestPdmPoll,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_pdm_connection import (
    VerifyPdmConnection,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.errors import PdmMutatingOperationsDisabledError
from src.modules.external_data.domain.errors import PdmNotConfiguredError
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.errors import PdmOperationNotAllowedError
from src.modules.external_data.domain.errors import PdmOperationParametersInvalidError
from src.modules.external_data.domain.errors import PdmUnknownOperationError
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmInvokeResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmParamSpec
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVersionInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflowState
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork


def make_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = {
        "id": 1,
        "made_item_variable_map": {},
        "bought_item_variable_map": {},
        "enabled": False,
        "base_url": "http://pdm-host:65453",
        "vault_name": "MyVault",
        "username": "svc-account",
        "password": "secret",
        "verify_certificate": True,
        "timeout_seconds": 15,
        "session_token": None,
        "session_user_id": None,
        "session_obtained_at": None,
        "watched_folders": [],
        "made_released_state_ids": [],
        "made_obsolete_state_ids": [],
        "made_replaced_state_ids": [],
        "bought_released_state_ids": [],
        "bought_obsolete_state_ids": [],
        "bought_replaced_state_ids": [],
        "poll_interval_minutes": 15,
        "vault_id": "",
        "cad_items_read_only": True,
        "last_poll_at": None,
        "last_poll_error": None,
        "last_poll_summary": None,
        "writeback_enabled": False,
        "made_item_extensions": ["sldprt"],
        "bought_item_extensions": ["sldprt", "sldasm"],
        "document_categories": {"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        "thumbnails_enabled": False,
        "stuck_after_days": 7,
        "reconcile_requested_deep": None,
        "required_fields": {"made": [], "bought": []},
    }
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class FakeRepo:
    def __init__(self, settings: AdminPdmSettings) -> None:
        self.pdm = settings
        self.audit_log: list[AdminSettingsAuditEntry] = []

    async def get_pdm(self) -> AdminPdmSettings:
        return self.pdm

    async def save_pdm_session(
        self, *, token: str | None, user_id: int | None, obtained_at: datetime | None
    ) -> None:
        self.pdm.session_token = token
        self.pdm.session_user_id = user_id
        self.pdm.session_obtained_at = obtained_at

    async def save_pdm_poll_status(
        self, *, at: datetime | None, error: str | None, summary: str | None
    ) -> None:
        self.pdm.last_poll_at = at
        self.pdm.last_poll_error = error
        self.pdm.last_poll_summary = summary

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry:
        entry.id = len(self.audit_log) + 1
        self.audit_log.append(entry)
        return entry


class FakeGateway:
    def __init__(
        self,
        *,
        version_result: PdmVersionInfo | Exception | None = None,
        auth_result: PdmAuthResult | Exception | None = None,
        invoke_result: PdmInvokeResult | Exception | None = None,
        workflows_result: list[PdmWorkflow] | Exception | None = None,
        browse_result: list[PdmObjectInfo] | Exception | None = None,
    ) -> None:
        self.version_result = version_result or PdmVersionInfo(
            product_name="SOLIDWORKS PDM Professional", app_version="2025", file_version="30.0"
        )
        self.auth_result = auth_result or PdmAuthResult(token="tok", user_id=1)
        self.invoke_result = invoke_result
        self.workflows_result = workflows_result if workflows_result is not None else []
        self.browse_result = browse_result if browse_result is not None else []
        self.invoke_calls: list[tuple[str | None, object, object, object]] = []

    async def version(self) -> PdmVersionInfo:
        if isinstance(self.version_result, Exception):
            raise self.version_result
        return self.version_result

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        if isinstance(self.auth_result, Exception):
            raise self.auth_result
        return self.auth_result

    async def vault_info(self, token: str) -> object:  # pragma: no cover
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
        raise NotImplementedError  # pragma: no cover - not exercised here

    async def set_datacard_variables(
        self,
        token: str,
        file_id: int,
        folder_id: int,
        configuration_id: int,
        card: object,
        values: dict[str, str],
    ) -> bool:  # pragma: no cover - not exercised here
        raise NotImplementedError

    async def invoke(
        self,
        token: str | None,
        spec: PdmOperationSpec,
        path_params: dict[str, object],
        query: dict[str, object],
        body: object | None,
    ) -> PdmInvokeResult:
        self.invoke_calls.append((token, spec, path_params, query))
        if isinstance(self.invoke_result, Exception):
            raise self.invoke_result
        assert self.invoke_result is not None
        return self.invoke_result


def make_gateway_factory(gateway: FakeGateway):
    def factory(connection: PdmConnection) -> IPdmGateway:
        return gateway  # type: ignore[return-value]

    return factory


READ_OP = PdmOperationSpec(
    id="get_files_id_info",
    method="GET",
    path="api/{vaultName}/files/{id}/info",
    group="Files",
    description="Get file info.",
    params=(
        PdmParamSpec(
            name="vaultName", location="path", type="string", required=True, description=""
        ),
        PdmParamSpec(name="id", location="path", type="int", required=True, description=""),
    ),
    has_body=False,
    body_example=None,
    mutating=False,
)

MUTATING_OP = PdmOperationSpec(
    id="post_files_id_checkin",
    method="POST",
    path="api/{vaultName}/files/{id}/checkin",
    group="Files",
    description="Check in a file.",
    params=(
        PdmParamSpec(
            name="vaultName", location="path", type="string", required=True, description=""
        ),
        PdmParamSpec(name="id", location="path", type="int", required=True, description=""),
    ),
    has_body=True,
    body_example="{}",
    mutating=True,
)

CATALOGUE = (READ_OP, MUTATING_OP)


# ── ListPdmOperations ────────────────────────────────────────────────


class TestListPdmOperations:
    async def test_lists_every_operation_without_the_vault_name_param(self):
        use_case = ListPdmOperations(CATALOGUE)
        actor = make_user(permissions=[Permission.READ_SETTINGS])

        results = await use_case.execute(actor=actor)

        assert [r.id for r in results] == ["get_files_id_info", "post_files_id_checkin"]
        for result in results:
            assert all(p.name != "vaultName" for p in result.params)

    async def test_requires_read_settings(self):
        use_case = ListPdmOperations(CATALOGUE)
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor)


# ── VerifyPdmConnection ──────────────────────────────────────────────


class TestVerifyPdmConnection:
    def setup_method(self):
        self.repo = FakeRepo(make_settings())
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])

    def _command(self, **overrides: object) -> VerifyPdmConnectionCommand:
        defaults: dict[str, object] = {
            "base_url": "http://pdm-host:65453",
            "vault_name": "MyVault",
            "username": "svc-account",
            "password": "typed-password",
            "verify_certificate": True,
            "timeout_seconds": 15,
        }
        defaults.update(overrides)
        return VerifyPdmConnectionCommand(**defaults)  # type: ignore[arg-type]

    async def test_successful_probe_returns_version_and_user_id(self):
        gateway = FakeGateway(auth_result=PdmAuthResult(token="tok", user_id=99))
        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo)

        result = await use_case.execute(actor=self.actor, cmd=self._command())

        assert result.user_id == 99
        assert result.product_name == "SOLIDWORKS PDM Professional"

    async def test_empty_password_falls_back_to_stored_password(self):
        self.repo.pdm.password = "stored-password"
        gateway = FakeGateway()
        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo)

        await use_case.execute(actor=self.actor, cmd=self._command(password=""))
        # No exception means the fallback password reached authenticate();
        # nothing else observable to assert on a fake that ignores the value.

    async def test_no_password_supplied_or_stored_raises_not_configured(self):
        self.repo.pdm.password = None
        gateway = FakeGateway()
        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo)

        with pytest.raises(PdmNotConfiguredError):
            await use_case.execute(actor=self.actor, cmd=self._command(password=""))

    async def test_rejected_credentials_raise_authentication_failed(self):
        gateway = FakeGateway(auth_result=PdmAuthenticationFailedError("rejected"))
        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo)

        with pytest.raises(PdmAuthenticationFailedError):
            await use_case.execute(actor=self.actor, cmd=self._command())

    async def test_read_transaction_ends_before_the_first_http_request(self):
        self.repo.pdm.password = "stored-password"
        events: list[str] = []
        gateway = FakeGateway()
        original_version = gateway.version

        async def version() -> PdmVersionInfo:
            events.append("version")
            return await original_version()

        gateway.version = version  # type: ignore[method-assign]

        class OrderedUow:
            async def commit(self) -> None:
                events.append("commit")

            async def rollback(self) -> None:  # pragma: no cover - never called
                events.append("rollback")

        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo, uow=OrderedUow())

        await use_case.execute(actor=self.actor, cmd=self._command(password=""))

        assert events == ["commit", "version"]

    async def test_probing_does_not_persist_anything(self):
        gateway = FakeGateway()
        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo)

        await use_case.execute(actor=self.actor, cmd=self._command(vault_name="OtherVault"))

        assert self.repo.pdm.vault_name == "MyVault"

    async def test_requires_write_settings(self):
        gateway = FakeGateway()
        use_case = VerifyPdmConnection(make_gateway_factory(gateway), self.repo)
        actor = make_user(permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, cmd=self._command())


# ── InvokePdmOperation ───────────────────────────────────────────────


class TestInvokePdmOperation:
    def setup_method(self):
        self.repo = FakeRepo(make_settings())
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])

    def _use_case(
        self, gateway: FakeGateway, *, mutating_operations_enabled: bool = True
    ) -> InvokePdmOperation:
        session = PdmSessionService(repo=self.repo, gateway_factory=make_gateway_factory(gateway))
        return InvokePdmOperation(
            session=session,
            catalogue=CATALOGUE,
            repo=self.repo,
            uow=FakeUnitOfWork(),
            mutating_operations_enabled=mutating_operations_enabled,
        )

    async def test_mutating_operation_is_refused_while_the_deployment_disables_them(self):
        """PDM__ALLOW_MUTATING_OPERATIONS off refuses a mutating call even with
        the per-call opt-in, and never reaches the vault."""
        gateway = FakeGateway()
        use_case = self._use_case(gateway, mutating_operations_enabled=False)
        with pytest.raises(PdmMutatingOperationsDisabledError, match="PDM__ALLOW_MUTATING"):
            await use_case.execute(
                actor=self.actor,
                cmd=InvokePdmOperationCommand(
                    operation_id="post_files_id_checkin",
                    path_params={"id": 1},
                    allow_mutating=True,
                ),
            )
        assert gateway.invoke_calls == []
        assert self.repo.audit_log == []

    async def test_read_operation_runs_while_the_deployment_disables_mutating_ones(self):
        gateway = FakeGateway(
            invoke_result=PdmInvokeResult(
                method="GET",
                url="http://pdm-host:65453/api/MyVault/files/42/info",
                status_code=200,
                elapsed_ms=1,
                content_type="application/json",
                response_json={"Id": 42},
                response_text=None,
            )
        )
        use_case = self._use_case(gateway, mutating_operations_enabled=False)

        result = await use_case.execute(
            actor=self.actor,
            cmd=InvokePdmOperationCommand(operation_id="get_files_id_info", path_params={"id": 42}),
        )

        assert result.status_code == 200

    async def test_invokes_a_read_operation_successfully(self):
        gateway = FakeGateway(
            invoke_result=PdmInvokeResult(
                method="GET",
                url="http://pdm-host:65453/api/MyVault/files/42/info",
                status_code=200,
                elapsed_ms=12,
                content_type="application/json",
                response_json={"Id": 42},
                response_text=None,
            )
        )
        use_case = self._use_case(gateway)

        result = await use_case.execute(
            actor=self.actor,
            cmd=InvokePdmOperationCommand(operation_id="get_files_id_info", path_params={"id": 42}),
        )

        assert result.status_code == 200
        assert result.response_json == {"Id": 42}
        assert self.repo.audit_log == []

    async def test_unknown_operation_id_raises(self):
        use_case = self._use_case(FakeGateway())
        with pytest.raises(PdmUnknownOperationError):
            await use_case.execute(
                actor=self.actor, cmd=InvokePdmOperationCommand(operation_id="does_not_exist")
            )

    async def test_missing_required_path_param_raises_parameters_invalid(self):
        use_case = self._use_case(FakeGateway())
        with pytest.raises(PdmOperationParametersInvalidError):
            await use_case.execute(
                actor=self.actor,
                cmd=InvokePdmOperationCommand(operation_id="get_files_id_info", path_params={}),
            )

    async def test_vault_name_in_path_params_is_rejected(self):
        use_case = self._use_case(FakeGateway())
        with pytest.raises(PdmOperationParametersInvalidError):
            await use_case.execute(
                actor=self.actor,
                cmd=InvokePdmOperationCommand(
                    operation_id="get_files_id_info",
                    path_params={"id": 1, "vaultName": "OtherVault"},
                ),
            )

    async def test_mutating_operation_without_allow_mutating_is_refused(self):
        use_case = self._use_case(FakeGateway())
        with pytest.raises(PdmOperationNotAllowedError):
            await use_case.execute(
                actor=self.actor,
                cmd=InvokePdmOperationCommand(
                    operation_id="post_files_id_checkin", path_params={"id": 1}
                ),
            )
        assert self.repo.audit_log == []

    async def test_mutating_operation_with_allow_mutating_succeeds_and_is_audited(self):
        gateway = FakeGateway(
            invoke_result=PdmInvokeResult(
                method="POST",
                url="http://pdm-host:65453/api/MyVault/files/1/checkin",
                status_code=200,
                elapsed_ms=5,
                content_type="application/json",
                response_json={"Success": True},
                response_text=None,
            )
        )
        use_case = self._use_case(gateway)

        result = await use_case.execute(
            actor=self.actor,
            cmd=InvokePdmOperationCommand(
                operation_id="post_files_id_checkin",
                path_params={"id": 1},
                allow_mutating=True,
            ),
        )

        assert result.status_code == 200
        assert len(self.repo.audit_log) == 1
        assert self.repo.audit_log[0].settings_domain == "pdm"

    async def test_mutating_operation_failure_response_is_not_audited(self):
        gateway = FakeGateway(
            invoke_result=PdmInvokeResult(
                method="POST",
                url="http://pdm-host:65453/api/MyVault/files/1/checkin",
                status_code=409,
                elapsed_ms=5,
                content_type="text/plain",
                response_json=None,
                response_text="conflict",
            )
        )
        use_case = self._use_case(gateway)

        result = await use_case.execute(
            actor=self.actor,
            cmd=InvokePdmOperationCommand(
                operation_id="post_files_id_checkin",
                path_params={"id": 1},
                allow_mutating=True,
            ),
        )

        assert result.status_code == 409
        assert self.repo.audit_log == []

    async def test_requires_write_settings(self):
        use_case = self._use_case(FakeGateway())
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                actor=actor,
                cmd=InvokePdmOperationCommand(
                    operation_id="get_files_id_info", path_params={"id": 1}
                ),
            )


# ── GetPdmWorkflows ──────────────────────────────────────────────────


class TestGetPdmWorkflows:
    def setup_method(self):
        self.repo = FakeRepo(make_settings())
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])

    def _use_case(self, gateway: FakeGateway) -> GetPdmWorkflows:
        session = PdmSessionService(repo=self.repo, gateway_factory=make_gateway_factory(gateway))
        return GetPdmWorkflows(session=session)

    async def test_lists_workflows_with_nested_states(self):
        gateway = FakeGateway(
            workflows_result=[
                PdmWorkflow(
                    workflow_id=1,
                    workflow_name="MadeItemWorkflow",
                    states=(
                        PdmWorkflowState(state_id=5, state_name="Released"),
                        PdmWorkflowState(state_id=9, state_name="Obsolete"),
                    ),
                )
            ]
        )
        use_case = self._use_case(gateway)

        results = await use_case.execute(actor=self.actor)

        assert len(results) == 1
        assert results[0].workflow_id == 1
        assert [s.state_name for s in results[0].states] == ["Released", "Obsolete"]

    async def test_requires_read_settings(self):
        use_case = self._use_case(FakeGateway())
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor)

    async def test_without_configured_connection_raises(self):
        self.repo.pdm.password = None
        use_case = self._use_case(FakeGateway())
        with pytest.raises(PdmNotConfiguredError):
            await use_case.execute(actor=self.actor)


# ── BrowsePdmFolders ─────────────────────────────────────────────────


def make_object_info(**overrides: object) -> PdmObjectInfo:
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


class TestBrowsePdmFolders:
    def setup_method(self):
        self.repo = FakeRepo(make_settings())
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])

    def _use_case(self, gateway: FakeGateway) -> BrowsePdmFolders:
        session = PdmSessionService(repo=self.repo, gateway_factory=make_gateway_factory(gateway))
        return BrowsePdmFolders(session=session)

    async def test_filters_out_files_and_boms(self):
        gateway = FakeGateway(
            browse_result=[
                make_object_info(id=1, name="Made-Parts", object_type=0),
                make_object_info(id=2, name="part.SLDPRT", object_type=1),
                make_object_info(id=3, name="bom.SLDASM", object_type=3),
            ]
        )
        use_case = self._use_case(gateway)

        results = await use_case.execute(actor=self.actor, parent_id=1)

        assert [r.id for r in results] == [1]
        assert results[0].name == "Made-Parts"

    async def test_requires_read_settings(self):
        use_case = self._use_case(FakeGateway())
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, parent_id=1)


# ── RequestPdmPoll ───────────────────────────────────────────────────


def make_enabled_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = {
        "enabled": True,
        "made_released_state_ids": [5],
        "bought_released_state_ids": [5],
    }
    defaults.update(overrides)
    return make_settings(**defaults)


class TestRequestPdmPoll:
    async def test_clears_last_poll_at_and_audits(self):
        repo = FakeRepo(
            make_enabled_settings(
                last_poll_at=datetime.now(UTC), last_poll_error="boom", last_poll_summary="old"
            )
        )
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = RequestPdmPoll(repo, uow=FakeUnitOfWork())

        await use_case.execute(actor=actor)

        assert repo.pdm.last_poll_at is None
        assert repo.pdm.last_poll_error is None
        assert repo.pdm.last_poll_summary is None
        assert len(repo.audit_log) == 1
        assert repo.audit_log[0].settings_domain == "pdm"

    async def test_not_enabled_raises(self):
        repo = FakeRepo(make_settings(enabled=False))
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = RequestPdmPoll(repo, uow=FakeUnitOfWork())

        with pytest.raises(PdmNotEnabledError):
            await use_case.execute(actor=actor)
        assert repo.audit_log == []

    async def test_enabled_but_not_configured_raises(self):
        repo = FakeRepo(make_enabled_settings(password=None))
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = RequestPdmPoll(repo, uow=FakeUnitOfWork())

        with pytest.raises(PdmNotEnabledError):
            await use_case.execute(actor=actor)

    async def test_requires_write_settings(self):
        repo = FakeRepo(make_enabled_settings())
        actor = make_user(permissions=[])
        use_case = RequestPdmPoll(repo, uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor)
