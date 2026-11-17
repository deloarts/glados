"""
Pydantic v2 wire models mirroring the SOLIDWORKS PDM Web API's PascalCase
JSON, for the operations Glados actually consumes (authenticate, version,
vault info, object search/info, configuration variables, workflows, the
write-back datacard, users and file transitions for PDM user matching and
ingest attribution). Every
model accepts the documented field name as its alias and carries a `to_*`
method that converts it into the corresponding frozen dataclass from
src/modules/external_data/ports/outbound/pdm_gateway_port.py, so nothing outside this module ever
sees PDM's PascalCase shape. `extra="ignore"` tolerates undocumented fields a
future PDM release might add.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUser
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUserExtended
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVersionInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflowState


def parse_pdm_datetime(value: object) -> datetime | None:
    """Parse one of PDM's ISO-8601 datetime strings (always carrying a UTC
    offset, e.g. "2024-11-27T09:51:59.716492-05:00") into an aware
    datetime. None and the empty string both mean "no value" and pass
    through as None; anything already a datetime is returned unchanged."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    raise TypeError(f"Cannot parse a PDM datetime from {value!r}")


class _PdmWireModel(BaseModel):
    """Base for every wire model: accept the PDM field name as alias, allow
    construction by the Python attribute name too (useful in tests), and
    ignore fields the official docs do not mention."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class AuthenticateResponse(_PdmWireModel):
    """Response of POST api/{vaultName}/authenticate. `Success` is not
    always present in the documented sample; treat only an explicit false
    as a rejection, absence as unknown."""

    success: bool | None = Field(default=None, alias="Success")
    jwt_string: str | None = Field(default=None, alias="JwtString")
    user_id: int | None = Field(default=None, alias="UserId")

    @property
    def is_authenticated(self) -> bool:
        return self.success is not False and bool(self.jwt_string)

    def to_auth_result(self) -> PdmAuthResult:
        return PdmAuthResult(token=self.jwt_string or "", user_id=self.user_id or 0)


class WebApiVersion(_PdmWireModel):
    """Response of the unauthenticated GET api/version/webapi probe."""

    sw_company: str = Field(default="", alias="SwCompany")
    sw_copyright: str = Field(default="", alias="SWCopyright")
    prod_name: str = Field(default="", alias="ProdName")
    prod_app_version: str = Field(default="", alias="ProdAppVersion")
    prod_file_version: str = Field(default="", alias="ProdFileVersion")

    def to_version_info(self) -> PdmVersionInfo:
        return PdmVersionInfo(
            product_name=self.prod_name,
            app_version=self.prod_app_version,
            file_version=self.prod_file_version,
        )


class VaultProp(_PdmWireModel):
    """Response of GET api/{vaultName}/info. `VaultID` is the GUID Glados
    stores as `vault_id`."""

    version: int = Field(default=0, alias="Version")
    vault_type: str = Field(default="", alias="VaultType")
    archive_server: str = Field(default="", alias="ArchiveServer")
    database_name: str = Field(default="", alias="DatabaseName")
    database_server: str = Field(default="", alias="DatabaseServer")
    vault_id: str = Field(default="", alias="VaultID")

    def to_vault_info(self) -> PdmVaultInfo:
        return PdmVaultInfo(
            vault_id=self.vault_id,
            version=self.version,
            vault_type=self.vault_type,
            archive_server=self.archive_server,
            database_name=self.database_name,
            database_server=self.database_server,
        )


class ObjectInfo(_PdmWireModel):
    """A file or folder, as returned by search, browse and the files/info*
    endpoints. PDM encodes the booleans (IsLocked, IsShared, IsToolbox,
    IsDeleted) as 0/1 integers; `to_object_info` converts them."""

    id: int = Field(alias="Id")
    name: str = Field(default="", alias="Name")
    size: int = Field(default=0, alias="Size")
    modified_date: datetime | None = Field(default=None, alias="ModifiedDate")
    version: int = Field(default=0, alias="Version")
    state: str = Field(default="", alias="State")
    state_id: int = Field(default=0, alias="StateId")
    parent_folder_id: int = Field(default=0, alias="ParentFolderId")
    path: str = Field(default="", alias="Path")
    type: int = Field(default=0, alias="Type")
    is_locked: int = Field(default=0, alias="IsLocked")
    locked_by: int = Field(default=0, alias="LockedBy")
    is_shared: int = Field(default=0, alias="IsShared")
    is_toolbox: int = Field(default=0, alias="IsToolbox")
    is_deleted: int = Field(default=0, alias="IsDeleted")

    @field_validator("modified_date", mode="before")
    @classmethod
    def _validate_modified_date(cls, value: object) -> datetime | None:
        return parse_pdm_datetime(value)

    def to_object_info(self) -> PdmObjectInfo:
        return PdmObjectInfo(
            id=self.id,
            name=self.name,
            size=self.size,
            modified_at=self.modified_date,
            version=self.version,
            state=self.state,
            state_id=self.state_id,
            parent_folder_id=self.parent_folder_id,
            path=self.path,
            object_type=self.type,
            is_locked=bool(self.is_locked),
            locked_by=self.locked_by,
            is_shared=bool(self.is_shared),
            is_toolbox=bool(self.is_toolbox),
            is_deleted=bool(self.is_deleted),
        )


class VariableInfo(_PdmWireModel):
    """One datacard variable value within a ConfigInfo. `VarValue` is
    nullable on the wire; PdmConfigVariables always carries a string, so
    None becomes ""."""

    var_id: int = Field(default=0, alias="VarId")
    var_name: str = Field(default="", alias="VarName")
    var_value: str | None = Field(default=None, alias="VarValue")
    var_type: int = Field(default=0, alias="VarType")
    mandatory: bool = Field(default=False, alias="Mandatory")
    version_free: bool = Field(default=False, alias="VersionFree")


class ConfigInfo(_PdmWireModel):
    """One configuration's variable values, as returned by the file
    variables endpoint. One file version can have several configurations;
    the caller decides which one to read: `@` first, falling back to the
    first configuration returned."""

    configuration_name: str = Field(default="", alias="ConfigurationName")
    configuration_id: int = Field(default=0, alias="ConfigurationId")
    models: list[VariableInfo] = Field(default_factory=list, alias="Models")

    def to_config_variables(self) -> PdmConfigVariables:
        return PdmConfigVariables(
            configuration_name=self.configuration_name,
            configuration_id=self.configuration_id,
            variables={m.var_name: (m.var_value or "") for m in self.models},
        )


class StateInfo(_PdmWireModel):
    state_id: int = Field(default=0, alias="StateId")
    state_name: str = Field(default="", alias="StateName")
    ignore_previous_permissions: int = Field(default=0, alias="IgnorePreviousPermissions")

    def to_workflow_state(self) -> PdmWorkflowState:
        return PdmWorkflowState(state_id=self.state_id, state_name=self.state_name)


class Workflow(_PdmWireModel):
    workflow_id: int = Field(default=0, alias="WorkflowId")
    workflow_name: str = Field(default="", alias="WorkflowName")
    states: list[StateInfo] = Field(default_factory=list, alias="States")

    def to_workflow(self) -> PdmWorkflow:
        return PdmWorkflow(
            workflow_id=self.workflow_id,
            workflow_name=self.workflow_name,
            states=tuple(s.to_workflow_state() for s in self.states),
        )


class WorkflowList(_PdmWireModel):
    """Response of GET api/{vaultName}/workflows."""

    workflows: list[Workflow] = Field(default_factory=list, alias="Workflows")

    def to_workflows(self) -> list[PdmWorkflow]:
        return [w.to_workflow() for w in self.workflows]


class DataCardVariableInfo(_PdmWireModel):
    """One variable within a DataCard's ConfigInfo_DataCard, GET
    .../datacard's richer sibling of VariableInfo (file_variables): adds
    ReadOnly, drops nothing Glados needs. `VarValue` is nullable on the
    wire; PdmDataCardVariable always carries a string, None becomes ""."""

    read_only: bool = Field(default=False, alias="ReadOnly")
    var_id: int = Field(default=0, alias="VarId")
    var_name: str = Field(default="", alias="VarName")
    var_value: str | None = Field(default=None, alias="VarValue")
    var_type: int = Field(default=0, alias="VarType")
    version_free: bool = Field(default=False, alias="VersionFree")
    multiline: bool = Field(default=False, alias="Multiline")
    mandatory: bool = Field(default=False, alias="Mandatory")

    def to_data_card_variable(self) -> PdmDataCardVariable:
        return PdmDataCardVariable(
            var_id=self.var_id,
            name=self.var_name,
            value=self.var_value or "",
            var_type=self.var_type,
            version_free=self.version_free,
            read_only=self.read_only,
            multiline=self.multiline,
            mandatory=self.mandatory,
        )


class DataCardConfigInfo(_PdmWireModel):
    """One configuration's variable definitions within a DataCard
    response: GET .../datacard's ConfigVarInfo entries."""

    models: list[DataCardVariableInfo] = Field(default_factory=list, alias="Models")
    configuration_name: str = Field(default="", alias="ConfigurationName")
    configuration_id: int = Field(default=0, alias="ConfigurationId")

    def to_data_card_configuration(self) -> PdmDataCardConfiguration:
        return PdmDataCardConfiguration(
            id=self.configuration_id,
            name=self.configuration_name,
            variables=tuple(m.to_data_card_variable() for m in self.models),
        )


class DataCard(_PdmWireModel):
    """Response of GET api/{vaultName}/files/{fileId}/{version}/datacard.
    `CardVariableInfo` (VariableValueOptions per variable) is not modelled,
    Glados never needs a dropdown's option list."""

    variables_with_write_all_configs: list[int] = Field(
        default_factory=list, alias="VariablesWithWriteAllConfigs"
    )
    config_var_info: list[DataCardConfigInfo] = Field(default_factory=list, alias="ConfigVarInfo")

    def to_data_card(self) -> PdmDataCard:
        return PdmDataCard(
            configurations=tuple(c.to_data_card_configuration() for c in self.config_var_info),
            variables_with_write_all_configs=tuple(self.variables_with_write_all_configs),
        )


class UserInfo(_PdmWireModel):
    """The minimal user reference PDM embeds in several responses:
    UserInfoFull.UserInfo, UserInfoExtended.UserInfo and
    HistoryTransition.User below."""

    user_id: int = Field(default=0, alias="UserId")
    user_name: str = Field(default="", alias="UserName")


class UserInfoFull(_PdmWireModel):
    """One entry of GET api/{vaultName}/users: a vault user."""

    user_info: UserInfo = Field(default_factory=UserInfo, alias="UserInfo")
    full_name: str = Field(default="", alias="FullName")
    initials: str = Field(default="", alias="Initials")

    def to_pdm_user(self) -> PdmUser:
        return PdmUser(
            id=self.user_info.user_id,
            username=self.user_info.user_name,
            full_name=self.full_name,
        )


class UserInfoExtended(_PdmWireModel):
    """Response of GET api/{vaultName}/users/{userId}/Extended."""

    user_info: UserInfo = Field(default_factory=UserInfo, alias="UserInfo")
    email: str = Field(default="", alias="Email")
    full_name: str = Field(default="", alias="FullName")
    initials: str = Field(default="", alias="Initials")
    phone: str = Field(default="", alias="Phone")
    cellphone: str = Field(default="", alias="Cellphone")

    def to_pdm_user_extended(self) -> PdmUserExtended:
        return PdmUserExtended(
            id=self.user_info.user_id,
            username=self.user_info.user_name,
            full_name=self.full_name,
            email=self.email,
        )


class HistoryTransition(_PdmWireModel):
    """One entry of GET .../files/{fileId}/transitions: the vault's own
    release history for a file. `Date` carries a UTC offset like every
    other PDM timestamp, parsed the same way ObjectInfo.ModifiedDate is.
    SourceState is not modelled, IngestPdmFile's attribution only ever
    reads the destination."""

    transition_id: int = Field(default=0, alias="TransitionId")
    version_no: int = Field(default=0, alias="VersionNo")
    comment: str = Field(default="", alias="Comment")
    date: datetime | None = Field(default=None, alias="Date")
    destination_state: StateInfo = Field(default_factory=StateInfo, alias="DestinationState")
    user: UserInfo = Field(default_factory=UserInfo, alias="User")

    @field_validator("date", mode="before")
    @classmethod
    def _validate_date(cls, value: object) -> datetime | None:
        return parse_pdm_datetime(value)
