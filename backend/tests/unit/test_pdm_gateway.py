"""
Unit tests for HttpxPdmGateway against httpx.MockTransport: no network, no
real vault. Covers the typed calls' request shapes and response parsing, the
generic error mapping (transport failure -> PdmUnavailableError, 401 ->
PdmSessionExpiredError, other non-2xx -> PdmApiError), authenticate's
collapsed failure mode, and invoke's console contract (path/query building
from a catalogued spec, no raise on non-2xx, truncation of oversized
responses).
"""

import json
from collections.abc import Callable

import httpx
import pytest

from src.modules.external_data.adapters.outbound.external.pdm.catalogue import find_operation
from src.modules.external_data.adapters.outbound.external.pdm.client import HttpxPdmGateway
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.errors import PdmOperationParametersInvalidError
from src.modules.external_data.domain.errors import PdmSessionExpiredError
from src.modules.external_data.domain.errors import PdmUnavailableError
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmSearchQuery

Handler = Callable[[httpx.Request], httpx.Response]


def make_connection(**overrides: object) -> PdmConnection:
    defaults: dict[str, object] = {
        "base_url": "http://pdm-host:65453",
        "vault_name": "MyVault",
        "verify_certificate": True,
        "timeout_seconds": 15,
    }
    defaults.update(overrides)
    return PdmConnection(**defaults)  # type: ignore[arg-type]


def make_gateway(handler: Handler, **connection_overrides: object) -> HttpxPdmGateway:
    return HttpxPdmGateway(
        make_connection(**connection_overrides), transport=httpx.MockTransport(handler)
    )


def get_operation(op_id: str) -> PdmOperationSpec:
    spec = find_operation(op_id)
    assert spec is not None, f"catalogue is missing {op_id}"
    return spec


# ── authenticate ─────────────────────────────────────────────────────


async def test_authenticate_success_returns_token_and_user_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/MyVault/authenticate"
        assert request.headers["accept"] == "application/json"
        assert json.loads(request.content) == {"Username": "admin", "Password": "secret"}
        return httpx.Response(200, json={"Success": True, "JwtString": "tok-123", "UserId": 7})

    gateway = make_gateway(handler)
    result = await gateway.authenticate("admin", "secret")

    assert result.token == "tok-123"
    assert result.user_id == 7


async def test_authenticate_rejected_when_success_is_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Success": False, "JwtString": "", "UserId": 0})

    gateway = make_gateway(handler)
    with pytest.raises(PdmAuthenticationFailedError):
        await gateway.authenticate("admin", "wrong")


async def test_authenticate_rejected_on_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    gateway = make_gateway(handler)
    with pytest.raises(PdmAuthenticationFailedError):
        await gateway.authenticate("admin", "wrong")


async def test_authenticate_rejected_when_jwt_string_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"UserId": 7})

    gateway = make_gateway(handler)
    with pytest.raises(PdmAuthenticationFailedError):
        await gateway.authenticate("admin", "secret")


async def test_authenticate_unreachable_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    gateway = make_gateway(handler)
    with pytest.raises(PdmUnavailableError):
        await gateway.authenticate("admin", "secret")


# ── version ──────────────────────────────────────────────────────────


async def test_version_parses_response_and_sends_no_authorization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/version/webapi"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "SwCompany": "Dassault Systemes",
                "SWCopyright": "(c)",
                "ProdName": "PDM Professional",
                "ProdAppVersion": "30.1.0",
                "ProdFileVersion": "30.1.0.1234",
            },
        )

    gateway = make_gateway(handler)
    info = await gateway.version()

    assert info.product_name == "PDM Professional"
    assert info.app_version == "30.1.0"
    assert info.file_version == "30.1.0.1234"


async def test_version_transport_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    gateway = make_gateway(handler)
    with pytest.raises(PdmUnavailableError):
        await gateway.version()


# ── search_files ─────────────────────────────────────────────────────


async def test_search_files_maps_recursive_latest_with_variables() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/MyVault/searchvariables"
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    gateway = make_gateway(handler)
    query = PdmSearchQuery(
        name="%",
        start_path="Made Parts",
        recursive=True,
        latest_only=True,
        variables=(("PDM.PartNumber", "1000-0001"),),
    )
    await gateway.search_files("tok", query)

    assert captured["body"] == {
        "Name": "%",
        "ObjectTypeCriteria": 1,
        "StartPath": "Made Parts",
        "PathCriteria": 2,
        "VersionCriteria": 1,
        "SearchOperand": 1,
        "Variables": [{"VariableName": "PDM.PartNumber", "SearchValue": "1000-0001"}],
    }


async def test_search_files_maps_non_recursive_all_versions_no_variables() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    gateway = make_gateway(handler)
    query = PdmSearchQuery(start_path="", recursive=False, latest_only=False, variables=())
    await gateway.search_files("tok", query)

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["PathCriteria"] == 1
    assert body["VersionCriteria"] == 2
    assert body["SearchOperand"] == 0
    assert body["Variables"] == []


async def test_search_files_parses_object_info() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "Id": 1,
                    "Name": "1000-0001.SLDPRT",
                    "Size": 1024,
                    "ModifiedDate": "2024-11-27T09:51:59.716492-05:00",
                    "Version": 3,
                    "State": "Released",
                    "StateId": 5,
                    "ParentFolderId": 8,
                    "Path": "Made Parts\\1000-0001.SLDPRT",
                    "Type": 1,
                    "IsLocked": 0,
                    "LockedBy": 0,
                    "IsShared": 1,
                    "IsToolbox": 0,
                    "IsDeleted": 0,
                }
            ],
        )

    gateway = make_gateway(handler)
    results = await gateway.search_files("tok", PdmSearchQuery())

    assert len(results) == 1
    item = results[0]
    assert item.id == 1
    assert item.is_locked is False
    assert item.is_shared is True
    assert item.modified_at is not None
    assert item.modified_at.utcoffset() is not None


# ── file_info_from_path ──────────────────────────────────────────────


async def test_file_info_from_path_returns_first_element() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == "Made Parts\\1000-0001.SLDPRT"
        return httpx.Response(
            200,
            json=[
                {
                    "Id": 42,
                    "Name": "1000-0001.SLDPRT",
                    "Size": 1,
                    "ModifiedDate": None,
                    "Version": 1,
                    "State": "In Work",
                    "StateId": 1,
                    "ParentFolderId": 1,
                    "Path": "Made Parts",
                    "Type": 1,
                    "IsLocked": 0,
                    "LockedBy": 0,
                    "IsShared": 0,
                    "IsToolbox": 0,
                    "IsDeleted": 0,
                }
            ],
        )

    gateway = make_gateway(handler)
    result = await gateway.file_info_from_path("tok", "Made Parts\\1000-0001.SLDPRT")

    assert result is not None
    assert result.id == 42
    assert result.modified_at is None


async def test_file_info_from_path_404_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    gateway = make_gateway(handler)
    assert await gateway.file_info_from_path("tok", "Made Parts\\missing.SLDPRT") is None


# ── browse_folder ────────────────────────────────────────────────────


async def test_browse_folder_builds_path_and_parses_object_info() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/MyVault/folders/8/browse"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json=[
                {
                    "Id": 8,
                    "Name": "Made-Parts",
                    "Size": 0,
                    "ModifiedDate": None,
                    "Version": 0,
                    "State": "",
                    "StateId": 0,
                    "ParentFolderId": 1,
                    "Path": "Made-Parts",
                    "Type": 0,
                    "IsLocked": 0,
                    "LockedBy": 0,
                    "IsShared": 0,
                    "IsToolbox": 0,
                    "IsDeleted": 0,
                }
            ],
        )

    gateway = make_gateway(handler)
    results = await gateway.browse_folder("tok", 8)

    assert len(results) == 1
    assert results[0].id == 8
    assert results[0].name == "Made-Parts"
    assert results[0].object_type == 0


async def test_browse_folder_401_raises_session_expired() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    gateway = make_gateway(handler)
    with pytest.raises(PdmSessionExpiredError):
        await gateway.browse_folder("tok", 1)


async def test_browse_folder_non_2xx_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    gateway = make_gateway(handler)
    with pytest.raises(PdmApiError):
        await gateway.browse_folder("tok", 1)


# ── file_variables ───────────────────────────────────────────────────


async def test_file_variables_two_configurations_none_becomes_empty_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/MyVault/files/42/3/variables"
        assert dict(request.url.params) == {"folderId": "9"}
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json=[
                {
                    "ConfigurationName": "@",
                    "ConfigurationId": 1,
                    "Models": [
                        {
                            "VarId": 1,
                            "VarName": "PDM.PartNumber",
                            "VarValue": "1000-0001",
                            "VarType": 1,
                            "Mandatory": True,
                            "VersionFree": False,
                        }
                    ],
                },
                {
                    "ConfigurationName": "Default",
                    "ConfigurationId": 2,
                    "Models": [
                        {
                            "VarId": 2,
                            "VarName": "PDM.Revision",
                            "VarValue": None,
                            "VarType": 1,
                            "Mandatory": False,
                            "VersionFree": True,
                        }
                    ],
                },
            ],
        )

    gateway = make_gateway(handler)
    result = await gateway.file_variables("tok", 42, 3, 9)

    assert len(result) == 2
    assert result[0].configuration_name == "@"
    assert result[0].variables == {"PDM.PartNumber": "1000-0001"}
    assert result[1].configuration_name == "Default"
    assert result[1].variables == {"PDM.Revision": ""}


# ── workflows / generic error mapping on a typed call ───────────────


async def test_workflows_parses_nested_states() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Workflows": [
                    {
                        "WorkflowId": 1,
                        "WorkflowName": "Made Item",
                        "States": [
                            {"StateId": 1, "StateName": "In Work", "IgnorePreviousPermissions": 0},
                            {"StateId": 2, "StateName": "Released", "IgnorePreviousPermissions": 1},
                        ],
                    }
                ]
            },
        )

    gateway = make_gateway(handler)
    workflows = await gateway.workflows("tok")

    assert len(workflows) == 1
    assert workflows[0].workflow_name == "Made Item"
    assert [s.state_name for s in workflows[0].states] == ["In Work", "Released"]


async def test_workflows_401_raises_session_expired() -> None:
    gateway = make_gateway(lambda request: httpx.Response(401, text="Unauthorized"))
    with pytest.raises(PdmSessionExpiredError):
        await gateway.workflows("tok")


async def test_vault_info_non_2xx_raises_api_error_with_status_and_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    gateway = make_gateway(handler)
    with pytest.raises(PdmApiError) as exc_info:
        await gateway.vault_info("tok")

    assert exc_info.value.status_code == 500
    assert exc_info.value.body == "internal error"


async def test_vault_info_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Version": 1,
                "VaultType": "Standard",
                "ArchiveServer": "archive-01",
                "DatabaseName": "MyVaultDb",
                "DatabaseServer": "sql-01",
                "VaultID": "e2a87d6d-8f9f-4c1c-a40c-39b81d9f9f56",
            },
        )

    gateway = make_gateway(handler)
    info = await gateway.vault_info("tok")

    assert info.vault_id == "e2a87d6d-8f9f-4c1c-a40c-39b81d9f9f56"
    assert info.archive_server == "archive-01"


# ── get_datacard / set_datacard_variables ───────────────────────────


async def test_get_datacard_parses_configurations_and_write_all_configs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/MyVault/files/42/3/datacard"
        assert dict(request.url.params) == {"folderId": "9"}
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={
                "VariablesWithWriteAllConfigs": [11],
                "ConfigVarInfo": [
                    {
                        "ConfigurationName": "@",
                        "ConfigurationId": 1,
                        "Models": [
                            {
                                "ReadOnly": False,
                                "VarId": 11,
                                "VarName": "Glados.Ids",
                                "VarValue": "[]",
                                "VarType": 1,
                                "Mandatory": False,
                                "VersionFree": True,
                            },
                            {
                                "ReadOnly": True,
                                "VarId": 12,
                                "VarName": "PDM.PartNumber",
                                "VarValue": "1000-0001",
                                "VarType": 1,
                                "Mandatory": True,
                                "VersionFree": False,
                            },
                        ],
                    }
                ],
            },
        )

    gateway = make_gateway(handler)
    card = await gateway.get_datacard("tok", 42, 3, 9)

    assert card.variables_with_write_all_configs == (11,)
    assert len(card.configurations) == 1
    config = card.configurations[0]
    assert config.id == 1
    assert config.name == "@"
    ids_var = next(v for v in config.variables if v.name == "Glados.Ids")
    assert ids_var.var_id == 11
    assert ids_var.value == "[]"
    assert ids_var.version_free is True
    part_number_var = next(v for v in config.variables if v.name == "PDM.PartNumber")
    assert part_number_var.version_free is False
    assert part_number_var.read_only is True


async def test_get_datacard_null_value_becomes_empty_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "VariablesWithWriteAllConfigs": [],
                "ConfigVarInfo": [
                    {
                        "ConfigurationName": "@",
                        "ConfigurationId": 1,
                        "Models": [
                            {
                                "ReadOnly": False,
                                "VarId": 1,
                                "VarName": "Glados.NewestRevisionSyncedAt",
                                "VarValue": None,
                                "VarType": 1,
                                "Mandatory": False,
                                "VersionFree": True,
                            }
                        ],
                    }
                ],
            },
        )

    gateway = make_gateway(handler)
    card = await gateway.get_datacard("tok", 1, 1, 0)

    assert card.configurations[0].variables[0].value == ""


def _card_with(*, config_id: int = 1, config_name: str = "@") -> PdmDataCard:
    return PdmDataCard(
        configurations=(
            PdmDataCardConfiguration(
                id=config_id,
                name=config_name,
                variables=(
                    PdmDataCardVariable(
                        var_id=11,
                        name="Glados.Ids",
                        value="[]",
                        var_type=1,
                        version_free=True,
                        read_only=False,
                    ),
                    PdmDataCardVariable(
                        var_id=13,
                        name="Glados.NewestRevisionSyncState",
                        value="",
                        var_type=1,
                        version_free=True,
                        read_only=False,
                    ),
                ),
            ),
        ),
        variables_with_write_all_configs=(),
    )


async def test_set_datacard_variables_builds_body_from_card_and_returns_true() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/MyVault/files/42/datacard"
        assert dict(request.url.params) == {"folderId": "9"}
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=True)

    gateway = make_gateway(handler)
    ok = await gateway.set_datacard_variables(
        "tok",
        42,
        9,
        1,
        _card_with(),
        {"Glados.Ids": "[1,2]", "Glados.NewestRevisionSyncState": "synced"},
    )

    assert ok is True
    body = captured["body"]
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["ConfigurationId"] == 1
    assert body[0]["ConfigurationName"] == "@"
    models_by_name = {m["VarName"]: m for m in body[0]["Models"]}
    assert models_by_name["Glados.Ids"] == {
        "ReadOnly": False,
        "Multiline": False,
        "VarId": 11,
        "VarName": "Glados.Ids",
        "VarValue": "[1,2]",
        "VarType": 1,
        "Mandatory": False,
        "VersionFree": True,
    }
    assert models_by_name["Glados.NewestRevisionSyncState"]["VarValue"] == "synced"


async def test_set_datacard_variables_skips_names_the_card_does_not_carry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert [m["VarName"] for m in body[0]["Models"]] == ["Glados.Ids"]
        return httpx.Response(200, json=True)

    gateway = make_gateway(handler)
    await gateway.set_datacard_variables(
        "tok", 42, 9, 1, _card_with(), {"Glados.Ids": "[]", "Glados.Unknown": "x"}
    )


async def test_set_datacard_variables_no_matching_variables_returns_false_without_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("no request should be sent when nothing matches")

    gateway = make_gateway(handler)
    ok = await gateway.set_datacard_variables(
        "tok", 42, 9, 1, _card_with(), {"Glados.Unknown": "x"}
    )

    assert ok is False


async def test_set_datacard_variables_false_response_is_returned() -> None:
    gateway = make_gateway(lambda request: httpx.Response(200, json=False))
    ok = await gateway.set_datacard_variables("tok", 42, 9, 1, _card_with(), {"Glados.Ids": "[]"})
    assert ok is False


async def test_set_datacard_variables_401_raises_session_expired() -> None:
    gateway = make_gateway(lambda request: httpx.Response(401))
    with pytest.raises(PdmSessionExpiredError):
        await gateway.set_datacard_variables("tok", 42, 9, 1, _card_with(), {"Glados.Ids": "[]"})


async def test_set_datacard_variables_non_2xx_raises_api_error() -> None:
    gateway = make_gateway(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(PdmApiError):
        await gateway.set_datacard_variables("tok", 42, 9, 1, _card_with(), {"Glados.Ids": "[]"})


# ── invoke ───────────────────────────────────────────────────────────


async def test_invoke_builds_path_and_query_for_file_variables() -> None:
    spec = get_operation("get_api_vaultname_files_fileid_version_variables_folderid_folderid")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/MyVault/files/42/3/variables"
        assert dict(request.url.params) == {"folderId": "9"}
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json=[])

    gateway = make_gateway(handler)
    result = await gateway.invoke("tok", spec, {"fileId": 42, "version": 3}, {"folderId": 9}, None)

    assert result.method == "GET"
    assert result.status_code == 200
    assert result.response_json == []
    assert "tok" not in result.url


async def test_invoke_sends_body_for_a_body_operation() -> None:
    spec = get_operation("post_api_vaultname_searchvariables")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/MyVault/searchvariables"
        assert "authorization" not in request.headers
        body = json.loads(request.content)
        assert body["Name"] == "%"
        return httpx.Response(200, json=[])

    gateway = make_gateway(handler)
    result = await gateway.invoke(None, spec, {}, {}, {"Name": "%", "ObjectTypeCriteria": 1})

    assert result.status_code == 200


async def test_invoke_skips_none_query_values() -> None:
    spec = get_operation("get_api_vaultname_files_fileid_version_variables_folderid_folderid")

    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {}
        return httpx.Response(200, json=[])

    gateway = make_gateway(handler)
    await gateway.invoke("tok", spec, {"fileId": 1, "version": 1}, {"folderId": None}, None)


async def test_invoke_percent_encodes_path_params() -> None:
    """A value can never add path segments, a query or a fragment."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.raw_path.decode())
        return httpx.Response(200, json={})

    gateway = make_gateway(handler)
    spec = get_operation("get_api_vaultname_files_fileid_version_variables_folderid_folderid")
    await gateway.invoke("tok", spec, {"fileId": "1/../../x?y#z", "version": 3}, {}, None)

    assert seen[0].startswith("/api/MyVault/files/1%2F..%2F..%2Fx%3Fy%23z/3/")


async def test_invoke_rejects_dot_segments_in_the_generic_uri() -> None:
    gateway = make_gateway(lambda request: httpx.Response(200, json={}))
    spec = get_operation("get_api_uri")
    with pytest.raises(PdmOperationParametersInvalidError):
        await gateway.invoke("tok", spec, {"uri": "MyVault/../other"}, {}, None)


async def test_invoke_missing_required_path_param_raises_parameters_invalid() -> None:
    spec = get_operation("get_api_vaultname_files_fileid_version_variables_folderid_folderid")
    gateway = make_gateway(lambda request: httpx.Response(200, json=[]))

    with pytest.raises(PdmOperationParametersInvalidError):
        await gateway.invoke("tok", spec, {"fileId": 42}, {}, None)


async def test_invoke_401_raises_session_expired() -> None:
    spec = get_operation("get_api_vaultname_workflows")
    gateway = make_gateway(lambda request: httpx.Response(401, text="no"))

    with pytest.raises(PdmSessionExpiredError):
        await gateway.invoke("tok", spec, {}, {}, None)


async def test_invoke_does_not_raise_on_other_non_2xx() -> None:
    spec = get_operation("get_api_vaultname_workflows")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    gateway = make_gateway(handler)
    result = await gateway.invoke("tok", spec, {}, {}, None)

    assert result.status_code == 500
    assert result.response_json == {"error": "boom"}


async def test_invoke_unreachable_raises_unavailable() -> None:
    spec = get_operation("get_api_vaultname_workflows")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    gateway = make_gateway(handler)
    with pytest.raises(PdmUnavailableError):
        await gateway.invoke("tok", spec, {}, {}, None)


async def test_invoke_truncates_oversized_text_response() -> None:
    spec = get_operation("get_api_vaultname_workflows")
    huge = "x" * (600 * 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=huge.encode(), headers={"content-type": "text/plain"})

    gateway = make_gateway(handler)
    result = await gateway.invoke("tok", spec, {}, {}, None)

    assert result.response_json is None
    assert result.response_text is not None
    assert result.response_text.endswith("… [truncated]")
    assert len(result.response_text) == 512 * 1024 + len("… [truncated]")


async def test_invoke_truncates_oversized_json_response_as_text() -> None:
    spec = get_operation("get_api_vaultname_workflows")
    huge_array = json.dumps(list(range(200_000)))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=huge_array.encode(), headers={"content-type": "application/json"}
        )

    gateway = make_gateway(handler)
    result = await gateway.invoke("tok", spec, {}, {}, None)

    assert result.response_json is None
    assert result.response_text is not None
    assert result.response_text.endswith("… [truncated]")


# ── users / file transitions (PDM user matching, ingest attribution) ──


async def test_list_users_parses_userinfofull_rows() -> None:
    """Sample JSON straight from the documented GET api/{vaultName}/users
    response."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/users")
        return httpx.Response(
            200,
            json=[
                {
                    "UserInfo": {"UserName": "jdoe", "UserId": 2},
                    "FullName": "Jane Doe",
                    "Initials": "JD",
                },
                {
                    "UserInfo": {"UserName": "svc-account", "UserId": 3},
                    "FullName": "Service Account",
                    "Initials": "SA",
                },
            ],
        )

    gateway = make_gateway(handler)
    users = await gateway.list_users("tok")

    assert [(u.id, u.username, u.full_name) for u in users] == [
        (2, "jdoe", "Jane Doe"),
        (3, "svc-account", "Service Account"),
    ]


async def test_list_users_401_raises_session_expired() -> None:
    gateway = make_gateway(lambda request: httpx.Response(401, text="Unauthorized"))
    with pytest.raises(PdmSessionExpiredError):
        await gateway.list_users("tok")


async def test_user_extended_parses_email() -> None:
    """Sample JSON from GET api/{vaultName}/users/{userId}/Extended."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/users/2/Extended")
        return httpx.Response(
            200,
            json={
                "UserInfo": {"UserName": "jdoe", "UserId": 2},
                "Email": "jane.doe@example.com",
                "FullName": "Jane Doe",
                "Initials": "JD",
                "Phone": "555-1234",
                "Cellphone": "555-5678",
            },
        )

    gateway = make_gateway(handler)
    extended = await gateway.user_extended("tok", 2)

    assert extended.id == 2
    assert extended.username == "jdoe"
    assert extended.full_name == "Jane Doe"
    assert extended.email == "jane.doe@example.com"


async def test_file_transitions_parses_destination_state_and_user() -> None:
    """Sample JSON from GET .../files/{fileId}/transitions, sends version
    and folderId as query parameters."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/files/42/transitions")
        assert request.url.params["version"] == "3"
        assert request.url.params["folderId"] == "7"
        return httpx.Response(
            200,
            json=[
                {
                    "TransitionId": 1,
                    "VersionNo": 3,
                    "Comment": "Released for production",
                    "Date": "2024-11-27T09:52:30.6765737-05:00",
                    "SourceState": {
                        "StateId": 1,
                        "StateName": "In Work",
                        "IgnorePreviousPermissions": 0,
                    },
                    "DestinationState": {
                        "StateId": 2,
                        "StateName": "Released",
                        "IgnorePreviousPermissions": 1,
                    },
                    "User": {"UserName": "jdoe", "UserId": 2},
                }
            ],
        )

    gateway = make_gateway(handler)
    transitions = await gateway.file_transitions("tok", 42, 3, 7)

    assert len(transitions) == 1
    transition = transitions[0]
    assert transition.destination_state_id == 2
    assert transition.destination_state_name == "Released"
    assert transition.user_id == 2
    assert transition.user_name == "jdoe"
    assert transition.comment == "Released for production"
    assert transition.occurred_at.isoformat() == "2024-11-27T09:52:30.676573-05:00"


async def test_file_transitions_drops_entries_with_no_date() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "TransitionId": 1,
                    "DestinationState": {"StateId": 2, "StateName": "Released"},
                    "User": {"UserName": "jdoe", "UserId": 2},
                    "Date": None,
                }
            ],
        )

    gateway = make_gateway(handler)
    assert await gateway.file_transitions("tok", 42, 3, 7) == []


async def test_file_transitions_401_raises_session_expired() -> None:
    gateway = make_gateway(lambda request: httpx.Response(401, text="Unauthorized"))
    with pytest.raises(PdmSessionExpiredError):
        await gateway.file_transitions("tok", 1, 1, 0)


# ── lifecycle ────────────────────────────────────────────────────────


async def test_close_and_context_manager() -> None:
    gateway = make_gateway(lambda request: httpx.Response(200, json={}))
    async with gateway as ctx:
        assert ctx is gateway
    await gateway.aclose()  # idempotent, must not raise

    # httpx refuses a request on a closed client.
    with pytest.raises(RuntimeError, match="client has been closed"):
        await gateway.version()
