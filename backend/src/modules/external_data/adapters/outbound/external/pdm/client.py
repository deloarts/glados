"""httpx-backed implementation of IPdmGateway against the SOLIDWORKS PDM
Professional Web API 2. One instance owns one persistent httpx.AsyncClient (base
URL, timeout and certificate verification fixed at construction, mirroring
the saved or unsaved connection it was built for); callers pass the bearer
token explicitly on every call, session lifecycle lives in the application
layer's PdmSessionService.

Every typed method (all but `invoke`) maps a transport failure to
PdmUnavailableError, a 401 to PdmSessionExpiredError and any other non-2xx
status to PdmApiError, so the session service can tell "not reachable" from
"needs a fresh token" from "PDM rejected the call". `authenticate` is the one
exception: every way it can fail, wrong status, unparsable body, a false
Success, a missing JwtString, collapses to PdmAuthenticationFailedError,
because a caller cannot usefully distinguish those cases. `invoke` is the
other exception: built for the admin API-test console, it deliberately does
not raise on a non-2xx status (the console wants to see PDM's own status and
body) and only intercepts 401 and transport failures.

The bearer token is never logged or put into an exception message.
set_datacard_variables posts only the variables being written, never the
whole card.
"""

import re
import time
from collections.abc import Mapping
from typing import Any
from typing import cast
from urllib.parse import quote

import httpx

from src.modules.external_data.adapters.outbound.external.pdm.models import AuthenticateResponse
from src.modules.external_data.adapters.outbound.external.pdm.models import ConfigInfo
from src.modules.external_data.adapters.outbound.external.pdm.models import DataCard
from src.modules.external_data.adapters.outbound.external.pdm.models import HistoryTransition
from src.modules.external_data.adapters.outbound.external.pdm.models import ObjectInfo
from src.modules.external_data.adapters.outbound.external.pdm.models import UserInfoExtended
from src.modules.external_data.adapters.outbound.external.pdm.models import UserInfoFull
from src.modules.external_data.adapters.outbound.external.pdm.models import VaultProp
from src.modules.external_data.adapters.outbound.external.pdm.models import WebApiVersion
from src.modules.external_data.adapters.outbound.external.pdm.models import WorkflowList
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.errors import PdmOperationParametersInvalidError
from src.modules.external_data.domain.errors import PdmSessionExpiredError
from src.modules.external_data.domain.errors import PdmUnavailableError
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmFileContent
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmInvokeResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmSearchQuery
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmTransition
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUser
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUserExtended
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVersionInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")

# Caps the admin console's response preview.
_MAX_RESPONSE_CHARS = 512 * 1024

# The catalogue's generic passthrough operations take a whole API path here.
_GENERIC_URI_PARAM = "uri"
_TRUNCATION_MARKER = "… [truncated]"

# Downloads stream and abort past this size, so a huge file is never held
# in memory.
_MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024


class HttpxPdmGateway:
    """IPdmGateway over one vault's Web API, reached through one long-lived
    httpx.AsyncClient. create_pdm_gateway caches one instance per
    PdmConnection and shares it across calls on the event loop."""

    def __init__(
        self, connection: PdmConnection, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._connection = connection
        self._client = httpx.AsyncClient(
            base_url=connection.base_url,
            timeout=connection.timeout_seconds,
            verify=connection.verify_certificate,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HttpxPdmGateway":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ── typed calls ──────────────────────────────────────────────────

    async def version(self) -> PdmVersionInfo:
        response = await self._call("GET", "api/version/webapi")
        self._raise_for_status(response)
        return WebApiVersion.model_validate(self._parse_json(response)).to_version_info()

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        response = await self._call(
            "POST",
            self._vault_path("authenticate"),
            json_body={"Username": username, "Password": password},
        )
        parsed: AuthenticateResponse | None = None
        if response.is_success:
            try:
                parsed = AuthenticateResponse.model_validate(response.json())
            except ValueError:
                parsed = None
        if parsed is None or not parsed.is_authenticated:
            raise PdmAuthenticationFailedError(
                f"PDM rejected the authentication request (HTTP {response.status_code})."
            )
        return parsed.to_auth_result()

    async def vault_info(self, token: str) -> PdmVaultInfo:
        response = await self._call("GET", self._vault_path("info"), token=token)
        self._raise_for_status(response)
        return VaultProp.model_validate(self._parse_json(response)).to_vault_info()

    async def search_files(self, token: str, query: PdmSearchQuery) -> list[PdmObjectInfo]:
        body = {
            "Name": query.name,
            "ObjectTypeCriteria": 1,
            "StartPath": query.start_path,
            "PathCriteria": 2 if query.recursive else 1,
            "VersionCriteria": 1 if query.latest_only else 2,
            "SearchOperand": 1 if query.variables else 0,
            "Variables": [
                {"VariableName": name, "SearchValue": value} for name, value in query.variables
            ],
        }
        response = await self._call(
            "POST", self._vault_path("searchvariables"), token=token, json_body=body
        )
        self._raise_for_status(response)
        return [
            ObjectInfo.model_validate(item).to_object_info() for item in self._parse_json(response)
        ]

    async def files_info(self, token: str, file_ids: list[int]) -> list[PdmObjectInfo]:
        response = await self._call(
            "POST", self._vault_path("files/info"), token=token, json_body=file_ids
        )
        self._raise_for_status(response)
        return [
            ObjectInfo.model_validate(item).to_object_info() for item in self._parse_json(response)
        ]

    async def file_info_from_path(self, token: str, path: str) -> PdmObjectInfo | None:
        response = await self._call(
            "POST", self._vault_path("files/infofrompath"), token=token, json_body=path
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        items = self._parse_json(response)
        if not items:
            return None
        return ObjectInfo.model_validate(items[0]).to_object_info()

    async def browse_folder(self, token: str, folder_id: int) -> list[PdmObjectInfo]:
        response = await self._call(
            "GET", self._vault_path(f"folders/{folder_id}/browse"), token=token
        )
        self._raise_for_status(response)
        return [
            ObjectInfo.model_validate(item).to_object_info() for item in self._parse_json(response)
        ]

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmConfigVariables]:
        path = self._vault_path(f"files/{file_id}/{version}/variables")
        response = await self._call("GET", path, token=token, params={"folderId": folder_id})
        self._raise_for_status(response)
        return [
            ConfigInfo.model_validate(item).to_config_variables()
            for item in self._parse_json(response)
        ]

    async def workflows(self, token: str) -> list[PdmWorkflow]:
        response = await self._call("GET", self._vault_path("workflows"), token=token)
        self._raise_for_status(response)
        return WorkflowList.model_validate(self._parse_json(response)).to_workflows()

    async def list_users(self, token: str) -> list[PdmUser]:
        response = await self._call("GET", self._vault_path("users"), token=token)
        self._raise_for_status(response)
        return [
            UserInfoFull.model_validate(item).to_pdm_user() for item in self._parse_json(response)
        ]

    async def user_extended(self, token: str, user_id: int) -> PdmUserExtended:
        response = await self._call(
            "GET", self._vault_path(f"users/{user_id}/Extended"), token=token
        )
        self._raise_for_status(response)
        return UserInfoExtended.model_validate(self._parse_json(response)).to_pdm_user_extended()

    async def file_transitions(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmTransition]:
        path = self._vault_path(f"files/{file_id}/transitions")
        response = await self._call(
            "GET", path, token=token, params={"version": version, "folderId": folder_id}
        )
        self._raise_for_status(response)
        transitions: list[PdmTransition] = []
        for item in self._parse_json(response):
            parsed = HistoryTransition.model_validate(item)
            if parsed.date is None:
                # An entry without a date cannot be ordered, so it is dropped.
                continue
            transitions.append(
                PdmTransition(
                    destination_state_id=parsed.destination_state.state_id,
                    destination_state_name=parsed.destination_state.state_name,
                    user_id=parsed.user.user_id,
                    user_name=parsed.user.user_name,
                    occurred_at=parsed.date,
                    comment=parsed.comment,
                )
            )
        return transitions

    # ── write-back to PDM ────────────────────────────────────────────

    async def get_datacard(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmDataCard:
        path = self._vault_path(f"files/{file_id}/{version}/datacard")
        response = await self._call("GET", path, token=token, params={"folderId": folder_id})
        self._raise_for_status(response)
        return DataCard.model_validate(self._parse_json(response)).to_data_card()

    async def set_datacard_variables(
        self,
        token: str,
        file_id: int,
        folder_id: int,
        configuration_id: int,
        card: PdmDataCard,
        values: dict[str, str],
    ) -> bool:
        configuration = next((c for c in card.configurations if c.id == configuration_id), None)
        by_name = {v.name: v for v in (configuration.variables if configuration else ())}
        # The flags are the card's own, echoed back: the Web API rejects a
        # variable whose flags differ from its definition (see PdmDataCardVariable).
        models = [
            {
                "ReadOnly": by_name[name].read_only,
                "Multiline": by_name[name].multiline,
                "VarId": by_name[name].var_id,
                "VarName": name,
                "VarValue": value,
                "VarType": by_name[name].var_type,
                "Mandatory": by_name[name].mandatory,
                "VersionFree": by_name[name].version_free,
            }
            for name, value in values.items()
            if name in by_name
        ]
        if not models:
            return False
        body = [
            {
                "Models": models,
                "ConfigurationName": configuration.name if configuration else "",
                "ConfigurationId": configuration_id,
            }
        ]
        response = await self._call(
            "POST",
            self._vault_path(f"files/{file_id}/datacard"),
            token=token,
            json_body=body,
            params={"folderId": folder_id},
        )
        self._raise_for_status(response)
        return bool(self._parse_json(response))

    # ── documents / thumbnails ────────────────────────────────────────

    async def download_file(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmFileContent:
        path = self._vault_path(f"files/{file_id}/{version}/download")
        content = await self._download(path, token, folder_id)
        if content is None:
            raise PdmApiError("PDM reported no content for this file.", status_code=404, body="")
        return content

    async def download_thumbnail(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmFileContent | None:
        path = self._vault_path(f"files/{file_id}/{version}/thumbnails")
        return await self._download(path, token, folder_id)

    async def _download(self, path: str, token: str, folder_id: int) -> PdmFileContent | None:
        """A redirect-based download, so redirects are followed here only;
        the console's `invoke` must see them raw. The body is streamed so the
        size cap holds."""
        try:
            async with self._client.stream(
                "GET",
                path,
                params={"folderId": folder_id},
                headers=self._auth_headers(token),
                follow_redirects=True,
            ) as response:
                if response.status_code == 401:
                    raise PdmSessionExpiredError("PDM session token was rejected (401).")
                if response.status_code == 404:
                    return None
                if not response.is_success:
                    await response.aread()
                    raise PdmApiError(
                        f"PDM call failed with HTTP {response.status_code}.",
                        status_code=response.status_code,
                        body=response.text,
                    )
                content_type = response.headers.get("content-type", "application/octet-stream")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_DOWNLOAD_BYTES:
                        raise PdmApiError(
                            f"PDM file exceeds the {_MAX_DOWNLOAD_BYTES} byte download cap.",
                            status_code=response.status_code,
                            body="",
                        )
                    chunks.append(chunk)
                return PdmFileContent(data=b"".join(chunks), content_type=content_type)
        except httpx.TransportError as exc:
            raise PdmUnavailableError(f"{type(exc).__name__}: {exc}") from exc

    # ── generic console call ─────────────────────────────────────────

    async def invoke(
        self,
        token: str | None,
        spec: PdmOperationSpec,
        path_params: Mapping[str, object],
        query: Mapping[str, object],
        body: object | None,
    ) -> PdmInvokeResult:
        base_path = spec.path.split("?", 1)[0]
        url_path = _PATH_PARAM_RE.sub(
            lambda m: self._resolve_path_param(m.group(1), path_params), base_path
        )
        # The parsed console body only holds JSON primitives.
        request_query = cast(
            "dict[str, str | int | float | bool | None]",
            {k: v for k, v in query.items() if v is not None},
        )
        json_body = body if (spec.has_body and body is not None) else None

        start = time.perf_counter()
        try:
            response = await self._client.request(
                spec.method,
                url_path,
                params=request_query,
                json=json_body,
                headers=self._auth_headers(token) if token else None,
            )
        except httpx.TransportError as exc:
            raise PdmUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if response.status_code == 401:
            raise PdmSessionExpiredError("PDM session token was rejected (401).")

        content_type = response.headers.get("content-type", "")
        response_json, response_text = self._capped_body(response, content_type)

        return PdmInvokeResult(
            method=spec.method,
            url=str(response.url),
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            content_type=content_type,
            response_json=response_json,
            response_text=response_text,
        )

    # ── helpers ──────────────────────────────────────────────────────

    def _vault_path(self, suffix: str) -> str:
        return f"api/{self._connection.vault_name}/{suffix}"

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _resolve_path_param(self, name: str, path_params: Mapping[str, object]) -> str:
        """A path parameter value, percent-encoded so it can never add path
        segments, a query or a fragment and so reach an operation the
        console does not list. The generic `uri` parameter is a path by
        definition and keeps its slashes, but not `..` segments."""
        if name == "vaultName":
            return quote(self._connection.vault_name, safe="")
        if name not in path_params:
            raise PdmOperationParametersInvalidError(f"Missing path parameter {name!r}.")
        value = str(path_params[name])
        if name == _GENERIC_URI_PARAM:
            if ".." in value.split("/"):
                raise PdmOperationParametersInvalidError(f"{name} must not contain '..' segments.")
            return quote(value, safe="/")
        return quote(value, safe="")

    async def _call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: object | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> httpx.Response:
        headers = self._auth_headers(token) if token is not None else None
        try:
            return await self._client.request(
                method, path, json=json_body, headers=headers, params=params
            )
        except httpx.TransportError as exc:
            raise PdmUnavailableError(f"{type(exc).__name__}: {exc}") from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise PdmSessionExpiredError("PDM session token was rejected (401).")
        if not response.is_success:
            raise PdmApiError(
                f"PDM call failed with HTTP {response.status_code}.",
                status_code=response.status_code,
                body=response.text,
            )

    def _parse_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise PdmApiError(
                f"PDM returned a non-JSON body for a {response.status_code} response.",
                status_code=response.status_code,
                body=response.text,
            ) from exc

    def _capped_body(
        self, response: httpx.Response, content_type: str
    ) -> tuple[object | None, str | None]:
        text = response.text
        if len(text) > _MAX_RESPONSE_CHARS:
            return None, text[:_MAX_RESPONSE_CHARS] + _TRUNCATION_MARKER
        if "json" in content_type.lower():
            try:
                return response.json(), None
            except ValueError:
                return None, text
        return None, text
