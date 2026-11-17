"""
Pure rules for drafts of meeting notes: the values a draft accepts, the
canonical form its texts are kept in, who sees it and how long it is kept.
A card's text goes through the card Markdown subset without any user or
file it could reference, so a draft never mentions anybody and never shows
an image; the reviewer adds mentions in the review if they want them. No
I/O.
"""

from datetime import datetime
from datetime import timedelta

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftAttendee
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftCard
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNewMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNextMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftTodo
from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingNotesDraftNotFoundError
from src.modules.workspace.domain.services.meeting_markdown import normalise_card_markdown
from src.modules.workspace.domain.services.meeting_rules import ATTENDEES_MAX
from src.modules.workspace.domain.services.meeting_rules import DECISION_MAX
from src.modules.workspace.domain.services.meeting_rules import LOCATION_MAX
from src.modules.workspace.domain.services.meeting_rules import NAME_MAX
from src.modules.workspace.domain.services.meeting_rules import SCOPE_MAX
from src.modules.workspace.domain.services.meeting_rules import TODO_NOTE_MAX
from src.modules.workspace.domain.services.meeting_rules import TODO_TITLE_MAX
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.services.meeting_tags import normalise_tags

CARDS_MAX = 100
DECISIONS_PER_CARD_MAX = 50
TODOS_PER_CARD_MAX = 50
OWNERS_PER_TODO_MAX = 10
PERSON_NAME_MAX = 200
EMAIL_MAX = 320
REVIEW_NOTE_MAX = 2_000

# A draft nobody applied or discarded within this time is deleted, since it
# keeps the names of people.
DRAFT_RETENTION = timedelta(days=30)


class MeetingNotesDraftRules:
    @staticmethod
    def assert_visible(draft: MeetingNotesDraft | None, actor: User) -> MeetingNotesDraft:
        """Only the draft's creator sees it; to anyone else it does not
        exist."""
        if draft is None or draft.creator_id != actor.id:
            raise MeetingNotesDraftNotFoundError("Meeting notes draft not found.")
        return draft

    @staticmethod
    def assert_target(
        meeting_id: int | None, project_id: int | None, product_id: int | None
    ) -> None:
        targets = [t for t in (meeting_id, project_id, product_id) if t is not None]
        if len(targets) != 1:
            raise MeetingInvalidInputError(
                "A draft adds to exactly one existing meeting or proposes a new meeting of "
                "exactly one project or product."
            )

    @staticmethod
    def expired_before(now: datetime) -> datetime:
        return now - DRAFT_RETENTION

    # ── Cleaning ──────────────────────────────────────────────────────

    @staticmethod
    def new_meeting(value: DraftNewMeeting) -> DraftNewMeeting:
        MeetingRules.assert_times(value.starts_at, value.ends_at)
        return DraftNewMeeting(
            name=MeetingRules.required_text(value.name, "name", NAME_MAX),
            starts_at=value.starts_at,
            ends_at=value.ends_at,
            location=MeetingRules.optional_text(value.location, "location", LOCATION_MAX),
            tags=normalise_tags(value.tags),
        )

    @staticmethod
    def next_meeting(value: DraftNextMeeting | None) -> DraftNextMeeting | None:
        if value is None:
            return None
        return DraftNextMeeting(
            day=value.day,
            start_time=value.start_time,
            location=MeetingRules.optional_text(
                value.location, "next meeting's place", LOCATION_MAX
            ),
        )

    @staticmethod
    def attendees(values: list[DraftAttendee]) -> list[DraftAttendee]:
        if len(values) > ATTENDEES_MAX:
            raise MeetingInvalidInputError(f"A meeting has at most {ATTENDEES_MAX} attendees.")
        return [
            DraftAttendee(
                name=MeetingRules.required_text(a.name, "attendee's name", PERSON_NAME_MAX),
                status=a.status,
                email=MeetingRules.optional_text(a.email, "attendee's e-mail address", EMAIL_MAX),
            )
            for a in values
        ]

    @staticmethod
    def cards(values: list[DraftCard]) -> list[DraftCard]:
        if not values:
            raise MeetingInvalidInputError("A draft needs at least one card.")
        if len(values) > CARDS_MAX:
            raise MeetingInvalidInputError(f"A draft has at most {CARDS_MAX} cards.")
        return [MeetingNotesDraftRules._card(card) for card in values]

    @staticmethod
    def _card(card: DraftCard) -> DraftCard:
        MeetingRules.assert_body(card.body)
        if len(card.decisions) > DECISIONS_PER_CARD_MAX:
            raise MeetingInvalidInputError(
                f"A card of a draft has at most {DECISIONS_PER_CARD_MAX} decisions."
            )
        if len(card.todos) > TODOS_PER_CARD_MAX:
            raise MeetingInvalidInputError(
                f"A card of a draft has at most {TODOS_PER_CARD_MAX} todos."
            )
        body = normalise_card_markdown(card.body, user_ids=set(), file_ids=set()).text
        return DraftCard(
            scope=MeetingRules.optional_text(card.scope, "scope", SCOPE_MAX),
            scope_icon=card.scope_icon,
            body=body,
            internal=card.internal,
            decisions=[
                MeetingRules.required_text(text, "decision", DECISION_MAX)
                for text in card.decisions
            ],
            todos=[MeetingNotesDraftRules._todo(todo) for todo in card.todos],
            review_note=MeetingNotesDraftRules.review_note(card.review_note),
        )

    @staticmethod
    def _todo(todo: DraftTodo) -> DraftTodo:
        if len(todo.owners) > OWNERS_PER_TODO_MAX:
            raise MeetingInvalidInputError(
                f"A todo of a draft has at most {OWNERS_PER_TODO_MAX} owners."
            )
        owners = [
            MeetingRules.required_text(name, "todo owner's name", PERSON_NAME_MAX)
            for name in todo.owners
        ]
        return DraftTodo(
            title=MeetingRules.required_text(todo.title, "todo's title", TODO_TITLE_MAX),
            note=MeetingRules.optional_text(todo.note, "todo's note", TODO_NOTE_MAX),
            due_date=todo.due_date,
            owners=list(dict.fromkeys(owners)),
        )

    @staticmethod
    def review_note(value: str | None) -> str | None:
        return MeetingRules.optional_text(value, "note for the reviewer", REVIEW_NOTE_MAX)
