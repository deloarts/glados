"""
Commands and results for the PDM vault access from the admin settings page: the
Web API console, workflows, folders, user linking, polling, file snapshots,
sync runs and reconciliation.
"""

from pydantic import BaseModel


class PdmParamResult(BaseModel):
    name: str
    location: str
    type: str
    required: bool
    description: str


class PdmOperationResult(BaseModel):
    id: str
    method: str
    path: str
    group: str
    description: str
    params: list[PdmParamResult]
    has_body: bool
    body_example: str | None
    mutating: bool


class InvokePdmOperationCommand(BaseModel):
    operation_id: str
    path_params: dict[str, object] = {}
    query: dict[str, object] = {}
    body: object | None = None
    allow_mutating: bool = False


class PdmInvokeResultDto(BaseModel):
    method: str
    url: str
    status_code: int
    elapsed_ms: int
    content_type: str
    response_json: object | None
    response_text: str | None


class PdmWorkflowStateResult(BaseModel):
    state_id: int
    state_name: str


class PdmWorkflowResult(BaseModel):
    workflow_id: int
    workflow_name: str
    states: list[PdmWorkflowStateResult]


class PdmFolderResult(BaseModel):
    id: int
    name: str
    path: str


class PdmUserResult(BaseModel):
    """One vault user row for the admin Match PDM Users dialog
    (GET /admin/settings/pdm/users); see ListPdmUsers and
    application.services.pdm_users for how linked_user_id and
    proposed_user_id are resolved. is_service_account flags the vault
    login the connection itself authenticates as; that row is never
    proposed or linkable."""

    pdm_user_id: int
    username: str
    full_name: str
    is_service_account: bool
    linked_user_id: int | None
    proposed_user_id: int | None


class LinkPdmUserEntryCommand(BaseModel):
    pdm_user_id: int
    user_id: int | None = None  # None unlinks


class LinkPdmUsersCommand(BaseModel):
    links: list[LinkPdmUserEntryCommand]
