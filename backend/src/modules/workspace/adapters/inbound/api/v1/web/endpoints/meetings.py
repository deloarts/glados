"""
Web surface endpoints for meetings: the meetings of a project or a product,
a meeting with its attendees, cards, decisions, todos and files, its
history and open points, card revisions, presence, files, scopes and the
tags in use.
Reading needs a signed-in user; the use cases check write:meetings and
manage:meetings for the writes.
"""

from typing import Any

from fastapi import Depends
from fastapi import Form
from fastapi import Query
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps import meetings as deps
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingCardCreateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingCardOrderRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingCardPresenceRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingCardResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingCardRevisionResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingCardRevisionRestoreRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingCardUpdateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingCreateRequest
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingDecisionRequest
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingDecisionResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingEventResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingFileResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingFileUpdateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingInvalidateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingListRowResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingOpenPointResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingRestoreRequest
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingScopeRenameRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingScopeRenameResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingScopeSuggestionsResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingTagSuggestionsResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingTodoRequest
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingTodoResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingUpdateRequest
from src.modules.workspace.application.dto.meeting_dto import CreateMeetingCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingCardCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingDecisionCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingListQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingScopeQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingTagQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoCommand
from src.modules.workspace.application.dto.meeting_dto import RenameMeetingScopeCommand
from src.modules.workspace.application.dto.meeting_dto import UpdateMeetingCommand
from src.modules.workspace.application.use_cases.meeting import cards
from src.modules.workspace.application.use_cases.meeting import files
from src.modules.workspace.application.use_cases.meeting import meetings
from src.modules.workspace.application.use_cases.meeting import scopes
from src.modules.workspace.application.use_cases.meeting import tags
from src.modules.workspace.application.use_cases.meeting import todos
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory

router = APIRouter()
scope_router = APIRouter()
tag_router = APIRouter()


def _as[T: BaseModel](model: type[T], result: BaseModel) -> T:
    return model.model_validate(result.model_dump())


def _all[T: BaseModel](model: type[T], results: list[Any]) -> list[T]:
    return [model.model_validate(r.model_dump()) for r in results]


# ── Meetings ──────────────────────────────────────────────────────────


@router.get("/", response_model=list[MeetingListRowResponse])
async def list_meetings(
    project_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    include_projects: bool = Query(
        default=True, description="For a product, add the meetings of each of its projects."
    ),
    include_invalid: bool = Query(default=True),
    tag: str | None = Query(
        default=None, max_length=200, description="Only the meetings that carry this tag."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: meetings.ListMeetings = Depends(deps.get_list_meetings_use_case),
) -> list[MeetingListRowResponse]:
    """The meetings of one project or one product, latest start first. Name
    exactly one of project_id and product_id. A tag matches in any case."""
    query = MeetingListQuery(
        project_id=project_id,
        product_id=product_id,
        include_projects=include_projects,
        include_invalid=include_invalid,
        tag=tag,
    )
    return _all(MeetingListRowResponse, await use_case.execute(actor, query))


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    body: MeetingCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.CreateMeeting = Depends(deps.get_create_meeting_use_case),
) -> MeetingResponse:
    cmd = CreateMeetingCommand.model_validate(body.model_dump())
    return _as(MeetingResponse, await use_case.execute(actor, cmd))


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def read_meeting(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.GetMeeting = Depends(deps.get_meeting_use_case),
) -> MeetingResponse:
    """The meeting with everything its page shows. Its owner tells the
    `/meetings/:id` redirect which page to open."""
    return _as(MeetingResponse, await use_case.execute(actor, meeting_id))


@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: int,
    body: MeetingUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.UpdateMeeting = Depends(deps.get_update_meeting_use_case),
) -> MeetingResponse:
    """Saves the meeting's facts and its attendees as listed."""
    cmd = UpdateMeetingCommand.model_validate(body.model_dump())
    return _as(MeetingResponse, await use_case.execute(actor, meeting_id, cmd))


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: int,
    expected_edit_version: int = Query(...),
    actor: User = Depends(get_current_active_user),
    use_case: meetings.DeleteMeeting = Depends(deps.get_delete_meeting_use_case),
) -> None:
    await use_case.execute(actor, meeting_id, expected_edit_version)


@router.post("/{meeting_id}/invalidate", response_model=MeetingResponse)
async def mark_meeting_invalid(
    meeting_id: int,
    body: MeetingInvalidateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.MarkMeetingInvalid = Depends(deps.get_mark_meeting_invalid_use_case),
) -> MeetingResponse:
    return _as(MeetingResponse, await use_case.execute(actor, meeting_id, body.reason))


@router.post("/{meeting_id}/restore", response_model=MeetingResponse)
async def restore_meeting(
    meeting_id: int,
    body: MeetingRestoreRequest,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.RestoreMeeting = Depends(deps.get_restore_meeting_use_case),
) -> MeetingResponse:
    return _as(MeetingResponse, await use_case.execute(actor, meeting_id, body.note))


@router.post(
    "/{meeting_id}/follow-up", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED
)
async def create_follow_up_meeting(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.CreateFollowUpMeeting = Depends(deps.get_create_follow_up_meeting_use_case),
) -> MeetingResponse:
    return _as(MeetingResponse, await use_case.execute(actor, meeting_id))


@router.get("/{meeting_id}/open-points", response_model=list[MeetingOpenPointResponse])
async def read_meeting_open_points(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.GetMeetingOpenPoints = Depends(deps.get_meeting_open_points_use_case),
) -> list[MeetingOpenPointResponse]:
    """The open todos of the meeting this one follows and of its
    predecessors."""
    return _all(MeetingOpenPointResponse, await use_case.execute(actor, meeting_id))


@router.get("/{meeting_id}/history", response_model=list[MeetingEventResponse])
async def read_meeting_history(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.GetMeetingHistory = Depends(deps.get_meeting_history_use_case),
) -> list[MeetingEventResponse]:
    return _all(MeetingEventResponse, await use_case.execute(actor, meeting_id))


@router.post("/{meeting_id}/attendees/{attendee_id}/anonymise", response_model=MeetingResponse)
async def anonymise_meeting_attendee(
    meeting_id: int,
    attendee_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: meetings.AnonymiseMeetingAttendee = Depends(
        deps.get_anonymise_meeting_attendee_use_case
    ),
) -> MeetingResponse:
    """Blanks a guest's name and e-mail address on the meeting."""
    return _as(MeetingResponse, await use_case.execute(actor, meeting_id, attendee_id))


# ── Cards ─────────────────────────────────────────────────────────────


@router.post(
    "/{meeting_id}/cards", response_model=MeetingCardResponse, status_code=status.HTTP_201_CREATED
)
async def create_meeting_card(
    meeting_id: int,
    body: MeetingCardCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: cards.CreateMeetingCard = Depends(deps.get_create_meeting_card_use_case),
) -> MeetingCardResponse:
    cmd = MeetingCardCommand.model_validate(body.model_dump())
    return _as(MeetingCardResponse, await use_case.execute(actor, meeting_id, cmd))


@router.put("/{meeting_id}/cards/order", response_model=list[MeetingCardResponse])
async def reorder_meeting_cards(
    meeting_id: int,
    body: MeetingCardOrderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: cards.ReorderMeetingCards = Depends(deps.get_reorder_meeting_cards_use_case),
) -> list[MeetingCardResponse]:
    return _all(MeetingCardResponse, await use_case.execute(actor, meeting_id, body.card_ids))


@router.get("/{meeting_id}/cards/{card_id}", response_model=MeetingCardResponse)
async def read_meeting_card(
    meeting_id: int,
    card_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: cards.GetMeetingCard = Depends(deps.get_meeting_card_use_case),
) -> MeetingCardResponse:
    return _as(MeetingCardResponse, await use_case.execute(actor, meeting_id, card_id))


@router.put("/{meeting_id}/cards/{card_id}", response_model=MeetingCardResponse)
async def update_meeting_card(
    meeting_id: int,
    card_id: int,
    body: MeetingCardUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: cards.UpdateMeetingCard = Depends(deps.get_update_meeting_card_use_case),
) -> MeetingCardResponse:
    """Saves the card. A card that moved since the version read answers 409;
    the client reads the card again and merges."""
    cmd = MeetingCardCommand.model_validate(body.model_dump())
    return _as(MeetingCardResponse, await use_case.execute(actor, meeting_id, card_id, cmd))


@router.delete("/{meeting_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_card(
    meeting_id: int,
    card_id: int,
    expected_edit_version: int = Query(...),
    actor: User = Depends(get_current_active_user),
    use_case: cards.DeleteMeetingCard = Depends(deps.get_delete_meeting_card_use_case),
) -> None:
    await use_case.execute(actor, meeting_id, card_id, expected_edit_version)


@router.get(
    "/{meeting_id}/cards/{card_id}/revisions", response_model=list[MeetingCardRevisionResponse]
)
async def read_meeting_card_revisions(
    meeting_id: int,
    card_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: cards.GetMeetingCardRevisions = Depends(deps.get_meeting_card_revisions_use_case),
) -> list[MeetingCardRevisionResponse]:
    """The card's revisions, newest first."""
    return _all(MeetingCardRevisionResponse, await use_case.execute(actor, meeting_id, card_id))


@router.post(
    "/{meeting_id}/cards/{card_id}/revisions/{revision_id}/restore",
    response_model=MeetingCardResponse,
)
async def restore_meeting_card_revision(
    meeting_id: int,
    card_id: int,
    revision_id: int,
    body: MeetingCardRevisionRestoreRequest,
    actor: User = Depends(get_current_active_user),
    use_case: cards.RestoreMeetingCardRevision = Depends(
        deps.get_restore_meeting_card_revision_use_case
    ),
) -> MeetingCardResponse:
    result = await use_case.execute(
        actor, meeting_id, card_id, revision_id, body.expected_edit_version
    )
    return _as(MeetingCardResponse, result)


@router.post("/{meeting_id}/cards/{card_id}/presence", status_code=status.HTTP_204_NO_CONTENT)
async def announce_meeting_card_presence(
    meeting_id: int,
    card_id: int,
    body: MeetingCardPresenceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: cards.AnnounceMeetingCardPresence = Depends(
        deps.get_announce_meeting_card_presence_use_case
    ),
) -> None:
    """A heartbeat of the card's editor, every 20 seconds while editing. The
    live stream carries it as a `meeting-card-presence` signal with the card
    id and the editor as its actor; viewers drop the editor 45 seconds after
    the last one or at once when `editing` is false."""
    await use_case.execute(actor, meeting_id, card_id, body.editing)


# ── Decisions ─────────────────────────────────────────────────────────


@router.post(
    "/{meeting_id}/cards/{card_id}/decisions",
    response_model=MeetingDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting_decision(
    meeting_id: int,
    card_id: int,
    body: MeetingDecisionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: todos.CreateMeetingDecision = Depends(deps.get_create_meeting_decision_use_case),
) -> MeetingDecisionResponse:
    cmd = MeetingDecisionCommand.model_validate(body.model_dump())
    return _as(MeetingDecisionResponse, await use_case.execute(actor, meeting_id, card_id, cmd))


@router.put("/{meeting_id}/decisions/{decision_id}", response_model=MeetingDecisionResponse)
async def update_meeting_decision(
    meeting_id: int,
    decision_id: int,
    body: MeetingDecisionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: todos.UpdateMeetingDecision = Depends(deps.get_update_meeting_decision_use_case),
) -> MeetingDecisionResponse:
    cmd = MeetingDecisionCommand.model_validate(body.model_dump())
    result = await use_case.execute(actor, meeting_id, decision_id, cmd)
    return _as(MeetingDecisionResponse, result)


@router.delete("/{meeting_id}/decisions/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_decision(
    meeting_id: int,
    decision_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: todos.DeleteMeetingDecision = Depends(deps.get_delete_meeting_decision_use_case),
) -> None:
    await use_case.execute(actor, meeting_id, decision_id)


# ── Todos ─────────────────────────────────────────────────────────────


@router.post(
    "/{meeting_id}/cards/{card_id}/todos",
    response_model=MeetingTodoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting_todo(
    meeting_id: int,
    card_id: int,
    body: MeetingTodoRequest,
    actor: User = Depends(get_current_active_user),
    use_case: todos.CreateMeetingTodo = Depends(deps.get_create_meeting_todo_use_case),
) -> MeetingTodoResponse:
    cmd = MeetingTodoCommand.model_validate(body.model_dump())
    return _as(MeetingTodoResponse, await use_case.execute(actor, meeting_id, card_id, cmd))


@router.put("/{meeting_id}/todos/{todo_id}", response_model=MeetingTodoResponse)
async def update_meeting_todo(
    meeting_id: int,
    todo_id: int,
    body: MeetingTodoRequest,
    actor: User = Depends(get_current_active_user),
    use_case: todos.UpdateMeetingTodo = Depends(deps.get_update_meeting_todo_use_case),
) -> MeetingTodoResponse:
    cmd = MeetingTodoCommand.model_validate(body.model_dump())
    return _as(MeetingTodoResponse, await use_case.execute(actor, meeting_id, todo_id, cmd))


@router.delete("/{meeting_id}/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_todo(
    meeting_id: int,
    todo_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: todos.DeleteMeetingTodo = Depends(deps.get_delete_meeting_todo_use_case),
) -> None:
    await use_case.execute(actor, meeting_id, todo_id)


@router.post("/{meeting_id}/todos/{todo_id}/done", response_model=MeetingTodoResponse)
async def tick_off_meeting_todo(
    meeting_id: int,
    todo_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: todos.SetMeetingTodoDone = Depends(deps.get_set_meeting_todo_done_use_case),
) -> MeetingTodoResponse:
    """Marks the todo done for everyone. Open to its owners as well."""
    return _as(MeetingTodoResponse, await use_case.execute(actor, meeting_id, todo_id, True))


@router.post("/{meeting_id}/todos/{todo_id}/reopen", response_model=MeetingTodoResponse)
async def reopen_meeting_todo(
    meeting_id: int,
    todo_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: todos.SetMeetingTodoDone = Depends(deps.get_set_meeting_todo_done_use_case),
) -> MeetingTodoResponse:
    return _as(MeetingTodoResponse, await use_case.execute(actor, meeting_id, todo_id, False))


# ── Files ─────────────────────────────────────────────────────────────


@router.get("/{meeting_id}/files", response_model=list[MeetingFileResponse])
async def list_meeting_files(
    meeting_id: int,
    _: User = Depends(get_current_active_user),
    use_case: files.GetMeetingFiles = Depends(deps.get_meeting_files_use_case),
) -> list[MeetingFileResponse]:
    return _all(MeetingFileResponse, await use_case.execute(meeting_id))


@router.post(
    "/{meeting_id}/files",
    response_model=MeetingFileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_meeting_file(
    meeting_id: int,
    file: UploadFile,
    category: MeetingFileCategory = Form(...),
    card_id: int | None = Form(default=None),
    actor: User = Depends(get_current_active_user),
    use_case: files.UploadMeetingFile = Depends(deps.get_upload_meeting_file_use_case),
) -> MeetingFileResponse:
    """Uploads an image or a PDF. An image pasted into a card names the card
    and is linked from its text as `![alt](file:<id>)`."""
    data, file_name, content_type = await read_upload(file)
    result = await use_case.execute(
        actor, meeting_id, data, file_name, content_type, category, card_id=card_id
    )
    return _as(MeetingFileResponse, result)


@router.get("/{meeting_id}/files/{file_id}")
async def download_meeting_file(
    meeting_id: int,
    file_id: int,
    disposition: str = "attachment",
    _: User = Depends(get_current_active_user),
    use_case: files.DownloadMeetingFile = Depends(deps.get_download_meeting_file_use_case),
) -> Response:
    file, data, content_type = await use_case.execute(meeting_id, file_id)
    return file_download_response(
        data, file.file_name, content_type=content_type, disposition=disposition
    )


@router.patch("/{meeting_id}/files/{file_id}", response_model=MeetingFileResponse)
async def rename_meeting_file(
    meeting_id: int,
    file_id: int,
    body: MeetingFileUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: files.RenameMeetingFile = Depends(deps.get_rename_meeting_file_use_case),
) -> MeetingFileResponse:
    result = await use_case.rename(actor, meeting_id, file_id, body.file_name)
    return _as(MeetingFileResponse, result)


@router.delete("/{meeting_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_file(
    meeting_id: int,
    file_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: files.DeleteMeetingFile = Depends(deps.get_delete_meeting_file_use_case),
) -> None:
    await use_case.execute(actor, meeting_id, file_id)


# ── Scopes ────────────────────────────────────────────────────────────


@scope_router.get("/", response_model=MeetingScopeSuggestionsResponse)
async def read_meeting_scope_suggestions(
    project_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    actor: User = Depends(get_current_active_user),
    use_case: scopes.GetMeetingScopeSuggestions = Depends(
        deps.get_meeting_scope_suggestions_use_case
    ),
) -> MeetingScopeSuggestionsResponse:
    """The scopes the owner's cards use, most used first, and the existing
    scope `q` nearly repeats. Name exactly one of project_id and
    product_id."""
    query = MeetingScopeQuery(project_id=project_id, product_id=product_id, query=q, limit=limit)
    return _as(MeetingScopeSuggestionsResponse, await use_case.execute(actor, query))


@scope_router.post("/rename", response_model=MeetingScopeRenameResponse)
async def rename_meeting_scope(
    body: MeetingScopeRenameRequest,
    actor: User = Depends(get_current_active_user),
    use_case: scopes.RenameMeetingScope = Depends(deps.get_rename_meeting_scope_use_case),
) -> MeetingScopeRenameResponse:
    """Renames the scope on every card of the owner's valid meetings that
    carries it."""
    cmd = RenameMeetingScopeCommand.model_validate(body.model_dump())
    return _as(MeetingScopeRenameResponse, await use_case.execute(actor, cmd))


# ── Tags ──────────────────────────────────────────────────────────────


@tag_router.get("/", response_model=MeetingTagSuggestionsResponse)
async def read_meeting_tag_suggestions(
    q: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=20, ge=1, le=100),
    actor: User = Depends(get_current_active_user),
    use_case: tags.GetMeetingTagSuggestions = Depends(deps.get_meeting_tag_suggestions_use_case),
) -> MeetingTagSuggestionsResponse:
    """The tags the meetings carry that contain `q`, in any case, most used
    first."""
    query = MeetingTagQuery(query=q, limit=limit)
    return _as(MeetingTagSuggestionsResponse, await use_case.execute(actor, query))
