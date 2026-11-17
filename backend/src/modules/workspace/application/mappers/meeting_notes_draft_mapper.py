"""Maps drafts of meeting notes and the people suggested for their names to
their results."""

from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftAttendeeResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftCardResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftNewMeetingResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftTodoResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import MeetingNotesDraftResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    MeetingNotesDraftSummaryResult,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import PersonMatchResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import PersonSuggestionResult
from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft
from src.modules.workspace.domain.services.person_name_matching import PersonCandidate
from src.modules.workspace.domain.services.person_name_matching import PersonMatch


def _suggestion(candidate: PersonCandidate) -> PersonSuggestionResult:
    return PersonSuggestionResult(kind=candidate.kind, id=candidate.id, name=candidate.name)


class MeetingNotesDraftMapper:
    @staticmethod
    def summary(draft: MeetingNotesDraft) -> MeetingNotesDraftSummaryResult:
        return MeetingNotesDraftSummaryResult(**MeetingNotesDraftMapper._summary_fields(draft))

    @staticmethod
    def _summary_fields(draft: MeetingNotesDraft) -> dict[str, object]:
        new = draft.new_meeting
        return {
            "id": draft.id,
            "public_id": draft.public_id,
            "created": draft.created,
            "token_name": draft.token_name,
            "meeting_id": draft.meeting_id,
            "meeting_number": draft.meeting_number,
            "meeting_name": draft.meeting_name,
            "project_id": draft.project_id,
            "product_id": draft.product_id,
            "owner_number": draft.owner_number,
            "name": new.name if new is not None else draft.meeting_name,
            "starts_at": new.starts_at if new is not None else None,
            "card_count": len(draft.cards),
            "decision_count": sum(len(c.decisions) for c in draft.cards),
            "todo_count": sum(len(c.todos) for c in draft.cards),
            "review_note": draft.review_note,
        }

    @staticmethod
    def detail(draft: MeetingNotesDraft, people: list[PersonMatch]) -> MeetingNotesDraftResult:
        new = draft.new_meeting
        following = draft.next_meeting
        return MeetingNotesDraftResult(
            **MeetingNotesDraftMapper._summary_fields(draft),
            new_meeting=(
                DraftNewMeetingResult(
                    name=new.name,
                    starts_at=new.starts_at,
                    ends_at=new.ends_at,
                    location=new.location,
                    tags=list(new.tags),
                )
                if new is not None
                else None
            ),
            attendees=[
                DraftAttendeeResult(name=a.name, status=a.status, email=a.email)
                for a in draft.attendees
            ],
            cards=[
                DraftCardResult(
                    scope=c.scope,
                    scope_icon=c.scope_icon,
                    body=c.body,
                    internal=c.internal,
                    decisions=list(c.decisions),
                    todos=[
                        DraftTodoResult(
                            title=t.title, note=t.note, due_date=t.due_date, owners=list(t.owners)
                        )
                        for t in c.todos
                    ],
                    review_note=c.review_note,
                )
                for c in draft.cards
            ],
            next_meeting_date=following.day if following is not None else None,
            next_meeting_time=following.start_time if following is not None else None,
            next_meeting_location=following.location if following is not None else None,
            people=[
                PersonMatchResult(
                    written=m.written,
                    candidates=[_suggestion(c) for c in m.candidates],
                    best=_suggestion(m.best) if m.best is not None else None,
                )
                for m in people
            ],
        )
