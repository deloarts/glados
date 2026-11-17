"""
Repository interfaces for meetings: the meeting with its attendees and
history, its cards with their revisions, mentions, decisions and todos, its
files, the snapshots of its printed, downloaded and sent notes, and the
queue of notifications that wait to be bundled.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingCardMention
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingEvent
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting import PendingMeetingNotification
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.services.meeting_scopes import ScopeUse
from src.modules.workspace.domain.services.meeting_tags import TagUse
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon


@dataclass(frozen=True)
class MeetingCardChip:
    """The scope of one card as a list row shows it."""

    scope: str | None
    icon: MeetingScopeIcon | None
    internal: bool


@dataclass(frozen=True)
class MeetingListRow:
    """One meeting of a list with what its row shows besides the meeting:
    the scopes and texts of its cards in order, and its open todos."""

    meeting: Meeting
    cards: list[MeetingCardChip]
    bodies: list[str]
    open_todo_count: int
    overdue_todo_count: int


@dataclass(frozen=True)
class ContactMeetingUsageRow:
    """A meeting a contact attends or owns a todo in."""

    contact_id: int
    meeting_id: int
    meeting_number: str
    name: str


@runtime_checkable
class IMeetingRepository(Protocol):
    async def get_by_id(self, id: int) -> Meeting | None:
        """The meeting with its attendees in order, deleted ones included."""
        ...

    async def get_by_public_id(self, public_id: UUID) -> Meeting | None: ...

    async def lock_for_update(self, id: int) -> None: ...

    async def save(self, meeting: Meeting) -> Meeting:
        """Writes the meeting and replaces its attendees and tags with the
        given ones, keeping the rows of attendees that carry their id."""
        ...

    async def next_number(self, template: str) -> str: ...

    async def list_rows(
        self,
        *,
        project_ids: list[int],
        product_ids: list[int],
        include_invalid: bool,
        today: date,
        tag: str | None = None,
    ) -> list[MeetingListRow]:
        """The meetings, not deleted, of the projects and products, latest
        start first, and with a tag only those that carry it in any case. A
        todo counts as overdue when its due date lies before `today`."""
        ...

    async def get_tag_uses(self) -> list[TagUse]:
        """Every tag spelling the meetings not deleted carry, with the number
        of meetings that carry it."""
        ...

    async def get_users(self, ids: set[int]) -> dict[int, User]:
        """The users of the ids that exist, inactive ones included."""
        ...

    async def add_event(self, event: MeetingEvent) -> MeetingEvent: ...

    async def get_events(self, meeting_id: int) -> list[MeetingEvent]:
        """The history of the meeting, newest first."""
        ...

    async def list_started_before(self, before: datetime) -> list[int]:
        """The ids of the meetings, deleted ones included, that started
        before the instant."""
        ...

    async def purge(self, meeting_id: int) -> None:
        """Removes the meeting and every row that belongs to it."""
        ...

    async def anonymise_contact_copies(self, contact_id: int, at: datetime) -> None:
        """Blanks the copies of the contact's name and e-mail address on the
        attendees and todo owners that name it."""
        ...

    async def get_contact_usage(self, contact_ids: list[int]) -> list[ContactMeetingUsageRow]:
        """The meetings not deleted that any of the contacts attends or owns a
        todo in, once per contact and meeting, latest start first."""
        ...


@runtime_checkable
class IMeetingCardRepository(Protocol):
    # ── Cards ─────────────────────────────────────────────────────────

    async def get_cards(self, meeting_id: int) -> list[MeetingCard]:
        """The cards in their order."""
        ...

    async def get_card(self, card_id: int) -> MeetingCard | None: ...

    async def lock_card(self, card_id: int) -> None: ...

    async def save_card(self, card: MeetingCard) -> MeetingCard: ...

    async def delete_card(self, card: MeetingCard) -> None: ...

    async def set_positions(self, meeting_id: int, card_ids: list[int]) -> None:
        """Numbers the cards in the given order, which names each card of
        the meeting once."""
        ...

    async def next_position(self, meeting_id: int) -> int: ...

    async def get_cards_with_scope(
        self, meeting_ids: list[int], scope: str
    ) -> list[MeetingCard]: ...

    async def get_scope_uses(self, meeting_ids: list[int]) -> list[ScopeUse]:
        """Every scope the cards of the meetings carry, with how many cards
        carry it and the icon most of them show."""
        ...

    # ── Revisions and mentions ────────────────────────────────────────

    async def last_revision(self, card_id: int) -> MeetingCardRevision | None: ...

    async def get_revisions(self, card_id: int) -> list[MeetingCardRevision]:
        """Newest first."""
        ...

    async def get_revision(self, revision_id: int) -> MeetingCardRevision | None: ...

    async def save_revision(self, revision: MeetingCardRevision) -> MeetingCardRevision: ...

    async def get_mentions(self, card_id: int) -> list[MeetingCardMention]: ...

    async def save_mention(self, mention: MeetingCardMention) -> MeetingCardMention: ...

    # ── Decisions ─────────────────────────────────────────────────────

    async def get_decisions(self, meeting_id: int) -> list[MeetingDecision]:
        """Every decision of the meeting, by card and position."""
        ...

    async def get_decision(self, decision_id: int) -> MeetingDecision | None: ...

    async def save_decision(self, decision: MeetingDecision) -> MeetingDecision: ...

    async def delete_decision(self, decision: MeetingDecision) -> None: ...

    async def next_decision_position(self, card_id: int) -> int: ...

    # ── Todos ─────────────────────────────────────────────────────────

    async def get_todos(self, meeting_id: int) -> list[MeetingTodo]:
        """Every todo of the meeting with its owners, by card and position."""
        ...

    async def get_todo(self, todo_id: int) -> MeetingTodo | None: ...

    async def save_todo(self, todo: MeetingTodo) -> MeetingTodo:
        """Writes the todo and replaces its owners with the given ones."""
        ...

    async def delete_todo(self, todo: MeetingTodo) -> None: ...

    async def next_todo_position(self, card_id: int) -> int: ...

    async def get_open_todos(self, meeting_ids: list[int]) -> list[MeetingTodo]:
        """The todos of the meetings that are not done, with their owners."""
        ...


@runtime_checkable
class IMeetingFileRepository(Protocol):
    """The file shape the shared attachment use cases need, with the
    meeting as the item, plus what purging and the orphan sweep read."""

    async def get_by_id(self, id: int) -> MeetingFile | None: ...

    async def get_by_item_id(self, item_id: int) -> list[MeetingFile]: ...

    async def get_by_item_id_and_category(
        self, item_id: int, category: Any
    ) -> list[MeetingFile]: ...

    async def get_by_item_ids(self, item_ids: list[int]) -> list[MeetingFile]: ...

    async def save(self, file: MeetingFile) -> MeetingFile: ...

    async def delete(self, file: MeetingFile) -> None: ...

    async def get_known_storage_paths(self, paths: list[str]) -> set[str]:
        """Which of the storage paths a file row names."""
        ...


@runtime_checkable
class IMeetingSnapshotRepository(Protocol):
    async def save(self, snapshot: MeetingSnapshot) -> MeetingSnapshot:
        """Adds the snapshot with the list of the contacts it names."""
        ...

    async def get_by_id(self, id: int) -> MeetingSnapshot | None: ...

    async def get_by_meeting(self, meeting_id: int) -> list[MeetingSnapshot]:
        """Newest first."""
        ...

    async def last_sent(self, meeting_id: int) -> MeetingSnapshot | None:
        """The snapshot of the meeting's latest send."""
        ...

    async def get_with_contact(self, contact_id: int) -> list[MeetingSnapshot]:
        """The snapshots that keep copies of the contact."""
        ...

    async def save_copies(self, snapshot: MeetingSnapshot) -> None:
        """Writes the cards, attendees and recipients of a snapshot back
        after their copies of names and addresses were blanked."""
        ...


@runtime_checkable
class IMeetingNotificationQueue(Protocol):
    async def add(
        self,
        *,
        meeting_id: int,
        recipient_id: int,
        actor_id: int,
        mentions: int,
        todos: int,
        now: datetime,
    ) -> None:
        """Adds mentions and todo assignments to what waits for the
        recipient in the meeting, starting the wait when nothing does."""
        ...

    async def get_due(self, started_before: datetime) -> list[PendingMeetingNotification]:
        """What has waited since before the instant, oldest first."""
        ...

    async def delete(self, pending: PendingMeetingNotification) -> None: ...
