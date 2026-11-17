"""
Web surface endpoints for the drafts of meeting notes AI agents prepare:
the caller's own drafts, one draft with the users and contacts suggested
for its names, applying the reviewed draft and discarding it. A draft is
seen only by its creator; applying needs write:meetings.
"""

from typing import Any

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps import meetings as deps
from src.modules.workspace.adapters.inbound.api.schemas.meeting_notes_draft_schema import (
    MeetingNotesDraftApplyRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_notes_draft_schema import (
    MeetingNotesDraftApplyResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_notes_draft_schema import (
    MeetingNotesDraftResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_notes_draft_schema import (
    MeetingNotesDraftSummaryResponse,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    ApplyMeetingNotesDraftCommand,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import MeetingNotesDraftListQuery
from src.modules.workspace.application.use_cases.meeting import notes_drafts

router = APIRouter()


def _as[T: BaseModel](model: type[T], result: BaseModel) -> T:
    return model.model_validate(result.model_dump())


def _all[T: BaseModel](model: type[T], results: list[Any]) -> list[T]:
    return [model.model_validate(r.model_dump()) for r in results]


@router.get("/", response_model=list[MeetingNotesDraftSummaryResponse])
async def list_meeting_notes_drafts(
    meeting_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    actor: User = Depends(get_current_active_user),
    use_case: notes_drafts.ListMeetingNotesDrafts = Depends(
        deps.get_list_meeting_notes_drafts_use_case
    ),
) -> list[MeetingNotesDraftSummaryResponse]:
    """The caller's drafts, newest first: all of them, or those that add to
    one meeting or propose a new meeting of one project or product."""
    query = MeetingNotesDraftListQuery(
        meeting_id=meeting_id, project_id=project_id, product_id=product_id
    )
    return _all(MeetingNotesDraftSummaryResponse, await use_case.execute(actor, query))


@router.get("/{draft_id}", response_model=MeetingNotesDraftResponse)
async def read_meeting_notes_draft(
    draft_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: notes_drafts.GetMeetingNotesDraft = Depends(deps.get_meeting_notes_draft_use_case),
) -> MeetingNotesDraftResponse:
    """The draft with the users, and for readers of contacts the contacts,
    that may be meant by each name it carries."""
    return _as(MeetingNotesDraftResponse, await use_case.execute(actor, draft_id))


@router.post("/{draft_id}/apply", response_model=MeetingNotesDraftApplyResponse)
async def apply_meeting_notes_draft(
    draft_id: int,
    body: MeetingNotesDraftApplyRequest,
    actor: User = Depends(get_current_active_user),
    use_case: notes_drafts.ApplyMeetingNotesDraft = Depends(
        deps.get_apply_meeting_notes_draft_use_case
    ),
) -> MeetingNotesDraftApplyResponse:
    """Writes the reviewed draft to its meeting, creating the meeting first
    for a draft of a new one, and deletes the draft."""
    cmd = ApplyMeetingNotesDraftCommand.model_validate(body.model_dump())
    return _as(MeetingNotesDraftApplyResponse, await use_case.execute(actor, draft_id, cmd))


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_meeting_notes_draft(
    draft_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: notes_drafts.DiscardMeetingNotesDraft = Depends(
        deps.get_discard_meeting_notes_draft_use_case
    ),
) -> None:
    await use_case.execute(actor, draft_id)
