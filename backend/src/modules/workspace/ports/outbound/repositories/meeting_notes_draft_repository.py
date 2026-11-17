"""Repository interface for the drafts of meeting notes AI agents prepare."""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft


@runtime_checkable
class IMeetingNotesDraftRepository(Protocol):
    async def save(self, draft: MeetingNotesDraft) -> MeetingNotesDraft: ...

    async def get_by_id(self, id: int) -> MeetingNotesDraft | None: ...

    async def get_by_creator(
        self,
        creator_id: int,
        *,
        meeting_id: int | None = None,
        project_id: int | None = None,
        product_id: int | None = None,
    ) -> list[MeetingNotesDraft]:
        """The creator's drafts, newest first: all of them, or those that add
        to one meeting or propose a new meeting of one project or product."""
        ...

    async def delete(self, draft: MeetingNotesDraft) -> None: ...

    async def delete_created_before(self, before: datetime) -> int:
        """Deletes the drafts created before `before` and says how many."""
        ...
