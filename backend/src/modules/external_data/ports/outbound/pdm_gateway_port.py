"""
Abstract access to the SOLIDWORKS PDM Professional Web API. The application
layer calls this, never httpx directly. Implementations live in
src/modules/external_data/adapters/outbound/external/pdm/.

The gateway is stateless about sessions: every call takes the bearer token
explicitly, and the application-level session service decides when to
authenticate again. That keeps token persistence and retry policy out of the
adapter and makes the gateway trivial to fake in tests.

The value types below are frozen dataclasses rather than the PDM wire models so
the application never depends on PDM's PascalCase JSON. Only the fields Glados
consumes are carried; everything else stays in the adapter.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class PdmConnection:
    """What is needed to reach one vault's Web API, without credentials."""

    base_url: str
    vault_name: str
    verify_certificate: bool
    timeout_seconds: int


@dataclass(frozen=True)
class PdmParamSpec:
    """One parameter of a catalogued operation. `location` is "path",
    "query" or "body"."""

    name: str
    location: str
    type: str
    required: bool
    description: str


@dataclass(frozen=True)
class PdmOperationSpec:
    """One operation of the PDM Web API as listed in the official help. `path`
    keeps the documented template including `{vaultName}` and the query
    placeholders; `id` is stable and used as the wire identifier by the admin
    console."""

    id: str
    method: str
    path: str
    group: str
    description: str
    params: tuple[PdmParamSpec, ...]
    has_body: bool
    body_example: str | None
    mutating: bool


@dataclass(frozen=True)
class PdmAuthResult:
    token: str
    user_id: int


@dataclass(frozen=True)
class PdmVersionInfo:
    product_name: str
    app_version: str
    file_version: str


@dataclass(frozen=True)
class PdmVaultInfo:
    """`vault_id` is the vault's GUID, the value stored on item rows."""

    vault_id: str
    version: int
    vault_type: str
    archive_server: str
    database_name: str
    database_server: str


@dataclass(frozen=True)
class PdmObjectInfo:
    """A file or folder as returned by search, browse and files/info.
    `object_type` is PDM's ObjectType: 0 folder, 1 file, 3 BOM."""

    id: int
    name: str
    size: int
    modified_at: datetime | None
    version: int
    state: str
    state_id: int
    parent_folder_id: int
    path: str
    object_type: int
    is_locked: bool
    locked_by: int
    is_shared: bool
    is_toolbox: bool
    is_deleted: bool


@dataclass(frozen=True)
class PdmConfigVariables:
    """Datacard variable values of one configuration of one file version.
    Values are always strings, PDM's null becomes ""."""

    configuration_name: str
    configuration_id: int
    variables: dict[str, str]


@dataclass(frozen=True)
class PdmWorkflowState:
    state_id: int
    state_name: str


@dataclass(frozen=True)
class PdmWorkflow:
    workflow_id: int
    workflow_name: str
    states: tuple[PdmWorkflowState, ...]


@dataclass(frozen=True)
class PdmSearchQuery:
    """Parameters for the vault-wide file search. `start_path` is relative to
    the vault root ("" = root), `recursive` includes subfolders, `latest_only`
    restricts to the latest version of each file, `variables` are
    (variable name, search value) pairs combined with AND."""

    name: str = ""
    start_path: str = ""
    recursive: bool = True
    latest_only: bool = True
    variables: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PdmDataCardVariable:
    """One datacard variable's definition and current value, as returned
    by GET .../datacard. Unlike PdmConfigVariables (file_variables' own
    per-configuration values, VarName -> VarValue only), this also
    carries `var_id` and `var_type`, both required to build the POST
    body set_datacard_variables sends back, which file_variables' payload
    cannot supply. The four flags are echoed back on that POST as well:
    the Web API checks each one against the card definition and answers
    403 ("var field 'VersionFree' : requires a 'True' value") for a flag
    that is left out, since a missing boolean reads as false."""

    var_id: int
    name: str
    value: str
    var_type: int
    version_free: bool
    read_only: bool
    multiline: bool = False
    mandatory: bool = False


@dataclass(frozen=True)
class PdmDataCardConfiguration:
    id: int
    name: str
    variables: tuple[PdmDataCardVariable, ...]


@dataclass(frozen=True)
class PdmDataCard:
    """One file version's full datacard: every configuration's variable
    definitions plus which variable ids PDM's admin tool marked "write to
    all configurations": set_datacard_variables reads
    `variables_with_write_all_configs` to decide whether a write targets
    one configuration or every one of them (see
    application.services.pdm_writeback.PdmWriteBack)."""

    configurations: tuple[PdmDataCardConfiguration, ...]
    variables_with_write_all_configs: tuple[int, ...]


@dataclass(frozen=True)
class PdmFileContent:
    """Raw bytes fetched from a redirect-based file endpoint (download,
    thumbnails), plus the content type the final response reported."""

    data: bytes
    content_type: str


@dataclass(frozen=True)
class PdmUser:
    """One vault user, as returned by GET api/{vaultName}/users; the
    admin console's user-matching dialog (ListPdmUsers/LinkPdmUsers), not
    an authentication concept."""

    id: int
    username: str
    full_name: str


@dataclass(frozen=True)
class PdmUserExtended:
    """GET api/{vaultName}/users/{userId}/Extended's richer sibling of
    PdmUser, fetched only for a not-yet-linked vault user whose username
    did not match any Glados user, to try an email match instead."""

    id: int
    username: str
    full_name: str
    email: str


@dataclass(frozen=True)
class PdmTransition:
    """One workflow transition from GET .../files/{fileId}/transitions,
    the vault's own release history for a file. IngestPdmFile reads this
    to attribute a created/revised/claimed/status outcome to the PDM user
    who performed the release; see application.services.pdm_users."""

    destination_state_id: int
    destination_state_name: str
    user_id: int
    user_name: str
    occurred_at: datetime
    comment: str


@dataclass(frozen=True)
class PdmInvokeResult:
    """Raw outcome of a generic operation call for the admin console. `url` is
    the full request URL without any credential."""

    method: str
    url: str
    status_code: int
    elapsed_ms: int
    content_type: str
    response_json: object | None
    response_text: str | None


@runtime_checkable
class IPdmGateway(Protocol):
    async def version(self) -> PdmVersionInfo:
        """Reachability probe, the only call that needs no token. Raises
        PdmUnavailableError when the server cannot be reached."""
        ...

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        """Log into the vault. Raises PdmAuthenticationFailedError when PDM
        rejected the credentials, PdmUnavailableError when it could not be
        asked."""
        ...

    async def vault_info(self, token: str) -> PdmVaultInfo: ...

    async def search_files(self, token: str, query: PdmSearchQuery) -> list[PdmObjectInfo]: ...

    async def files_info(self, token: str, file_ids: list[int]) -> list[PdmObjectInfo]: ...

    async def file_info_from_path(self, token: str, path: str) -> PdmObjectInfo | None: ...

    async def browse_folder(self, token: str, folder_id: int) -> list[PdmObjectInfo]:
        """One level of a folder's contents (files, subfolders and BOMs),
        for the admin settings page's watched-folder picker."""
        ...

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmConfigVariables]: ...

    async def workflows(self, token: str) -> list[PdmWorkflow]: ...

    async def list_users(self, token: str) -> list[PdmUser]:
        """GET .../users: every user of the vault, for the admin console's
        PDM/Glados user matching dialog (ListPdmUsers)."""
        ...

    async def user_extended(self, token: str, user_id: int) -> PdmUserExtended:
        """GET .../users/{userId}/Extended: one vault user's email, used
        only as ListPdmUsers' fallback match for a user a username guess
        did not resolve."""
        ...

    async def file_transitions(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmTransition]:
        """GET .../files/{fileId}/transitions: the file's workflow history,
        for IngestPdmFile's PDM-releaser attribution (see PdmTransition)."""
        ...

    async def get_datacard(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmDataCard:
        """The full datacard (every configuration's variable definitions,
        including VarId/VarType/VersionFree) for one file version: the
        write-back path's own read, richer than file_variables() and used
        nowhere else. See application.services.pdm_writeback.PdmWriteBack."""
        ...

    async def set_datacard_variables(
        self,
        token: str,
        file_id: int,
        folder_id: int,
        configuration_id: int,
        card: PdmDataCard,
        values: dict[str, str],
    ) -> bool:
        """Writes `values` (datacard variable name -> new value) onto the
        configuration `configuration_id`. `card` is the datacard the
        caller already fetched via get_datacard (it needs one anyway, to
        verify the variables it is about to write exist and are
        version-free); this resolves each named variable's VarId/VarType
        and flags from it and POSTs only those variables, the documented
        `VariableInfo_DataCard` shape with the card's own `ReadOnly`/
        `Multiline`/`Mandatory`/`VersionFree`, never the whole card. A
        name in `values` the card does not carry under this configuration
        is skipped. Returns the Web API's own boolean
        success response."""
        ...

    async def download_file(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmFileContent:
        """The file's own content (GET .../download?folderId=, a redirect
        the adapter follows), for a `documents` watched folder's export;
        see application.use_cases.pdm.pdm_documents.PdmDocumentSync. Raises
        PdmApiError when PDM reports no content (e.g. 404)."""
        ...

    async def download_thumbnail(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmFileContent | None:
        """The file's rendered PDM thumbnail (GET .../thumbnails?folderId=,
        a redirect the adapter follows), or None when PDM has none (most
        vaults, absent a Convert task); see application.services.
        pdm_documents.PdmThumbnails. Both this and download_file cap the
        response at 64 MiB."""
        ...

    async def invoke(
        self,
        token: str | None,
        spec: PdmOperationSpec,
        path_params: Mapping[str, object],
        query: Mapping[str, object],
        body: object | None,
    ) -> PdmInvokeResult:
        """Call any catalogued operation generically. Every method above maps
        a 401 to PdmSessionExpiredError and other failures to PdmApiError or
        PdmUnavailableError; `invoke` does the same so the session service can
        refresh the token transparently.

        `path_params`/`query` are `Mapping` rather than `dict` because
        `invoke` only ever reads them (never mutates its caller's dict);
        the value type stays `object` because the admin console's request
        body (`PdmInvokeRequest.path_params`/`.query`, both
        `dict[str, object]`) carries whatever JSON the operator typed in,
        with no value-shape validation beyond "JSON-decodable"."""
        ...


@runtime_checkable
class IPdmGatewayFactory(Protocol):
    def __call__(self, connection: PdmConnection) -> IPdmGateway:
        """Build a gateway for the given connection. A factory rather than a
        single injected gateway because the admin test-connection endpoint
        must probe settings that are not the persisted ones."""
        ...
