"""
Unit tests for GetPdmTriggerConfig: the API-key surface's trigger config
read (GET {API_KEY}/pdm/config). No database, no HTTP, no real gateway;
these tests only exercise the use case's own permission check,
enabled/configured gate, and released-state-id-to-name resolution.
"""

from typing import Any

import pytest

from src.modules.external_data.application.use_cases.pdm.get_pdm_trigger_config import (
    GetPdmTriggerConfig,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflowState
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories

MADE_FOLDER = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may trigger a PDM sync unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.USE_PDM_ADDIN]
    return factories.make_user(permissions=permissions, **overrides)


def make_pdm_settings(
    *,
    enabled: bool = True,
    made_released_state_ids: list[int] | None = None,
    bought_released_state_ids: list[int] | None = None,
) -> AdminPdmSettings:
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
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
        watched_folders=[MADE_FOLDER],
        made_released_state_ids=made_released_state_ids
        if made_released_state_ids is not None
        else [10],
        made_obsolete_state_ids=[20],
        made_replaced_state_ids=[30],
        bought_released_state_ids=bought_released_state_ids
        if bought_released_state_ids is not None
        else [11],
        bought_obsolete_state_ids=[21],
        bought_replaced_state_ids=[31],
        poll_interval_minutes=15,
        vault_id="V1",
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


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm


class FakeGateway:
    def __init__(self, workflows: list[PdmWorkflow] | None = None) -> None:
        self._workflows = workflows or []
        self.workflows_calls = 0

    async def workflows(self, token: str) -> list[PdmWorkflow]:
        self.workflows_calls += 1
        return self._workflows


class FakeSession:
    def __init__(self, gateway: FakeGateway) -> None:
        self._gateway = gateway

    async def call(self, fn):
        return await fn(self._gateway, "token")


def make_rig(
    *, pdm_settings: AdminPdmSettings | None = None, gateway: FakeGateway | None = None
) -> tuple[GetPdmTriggerConfig, FakeGateway, FakeAdminSettingsRepository]:
    gw = gateway or FakeGateway()
    settings_repo = FakeAdminSettingsRepository(pdm_settings or make_pdm_settings())
    use_case = GetPdmTriggerConfig(session=FakeSession(gw), admin_settings_repo=settings_repo)
    return use_case, gw, settings_repo


class TestPermissionAndEnablement:
    async def test_missing_permission_raises(self) -> None:
        use_case, _, _ = make_rig()
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_user(permissions=[]))

    async def test_disabled_raises(self) -> None:
        use_case, _, _ = make_rig(pdm_settings=make_pdm_settings(enabled=False))
        with pytest.raises(PdmNotEnabledError):
            await use_case.execute(make_user())


class TestReleaseStateNames:
    async def test_names_resolved_and_deduped_across_two_workflows(self) -> None:
        gw = FakeGateway(
            workflows=[
                PdmWorkflow(
                    workflow_id=1,
                    workflow_name="Made Workflow",
                    states=(
                        PdmWorkflowState(state_id=10, state_name="Released"),
                        PdmWorkflowState(state_id=20, state_name="Obsolete"),
                    ),
                ),
                PdmWorkflow(
                    workflow_id=2,
                    workflow_name="Bought Workflow",
                    states=(
                        # Same name as the made workflow's own released
                        # state: the result dedupes by name, not by id.
                        PdmWorkflowState(state_id=11, state_name="Released"),
                        PdmWorkflowState(state_id=21, state_name="Obsolete"),
                    ),
                ),
            ]
        )
        settings = make_pdm_settings(made_released_state_ids=[10], bought_released_state_ids=[11])
        use_case, _, _ = make_rig(pdm_settings=settings, gateway=gw)

        result = await use_case.execute(make_user())

        assert result.vault_name == "MyVault"
        assert result.release_state_names == ["Released"]

    async def test_unknown_ids_are_silently_dropped(self) -> None:
        gw = FakeGateway(
            workflows=[
                PdmWorkflow(
                    workflow_id=1,
                    workflow_name="Made Workflow",
                    states=(PdmWorkflowState(state_id=10, state_name="Released"),),
                )
            ]
        )
        settings = make_pdm_settings(
            made_released_state_ids=[10, 999], bought_released_state_ids=[]
        )
        use_case, _, _ = make_rig(pdm_settings=settings, gateway=gw)

        result = await use_case.execute(make_user())

        assert result.release_state_names == ["Released"]

    async def test_names_are_sorted_and_case_preserved(self) -> None:
        gw = FakeGateway(
            workflows=[
                PdmWorkflow(
                    workflow_id=1,
                    workflow_name="Workflow",
                    states=(
                        PdmWorkflowState(state_id=10, state_name="zReleased"),
                        PdmWorkflowState(state_id=11, state_name="Active"),
                    ),
                )
            ]
        )
        settings = make_pdm_settings(made_released_state_ids=[10, 11], bought_released_state_ids=[])
        use_case, _, _ = make_rig(pdm_settings=settings, gateway=gw)

        result = await use_case.execute(make_user())

        assert result.release_state_names == ["Active", "zReleased"]
