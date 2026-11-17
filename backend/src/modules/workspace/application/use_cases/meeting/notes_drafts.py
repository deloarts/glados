"""
The drafts of meeting notes AI agents prepare: an agent submits one, its
creator lists, reads, applies or discards it, and drafts past their
retention are deleted. Only the creator sees a draft. Submitting and
applying need write:meetings and a meeting that is not invalid.

Reading a draft suggests a user or contact for each name it carries. The
contacts offered are those linked to the meeting's project or product and
the contacts already on the meeting, and only to a reader of contacts.

Applying writes the reviewed form the person sends, never the stored draft
as it is: it creates the new meeting or loads the existing one, adds the
attendees the form lists, appends its cards with their decisions and
todos, queues the notifications of the users it assigns todos to, records
one history event and deletes the draft, all in one commit.
"""

from dataclasses import dataclass

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.meeting_dto import CreateMeetingCommand
from src.modules.workspace.application.dto.meeting_dto import MeetingAttendeeInput
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    ApplyMeetingNotesDraftCommand,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    ApplyMeetingNotesDraftResult,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    CreateMeetingNotesDraftCommand,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import MeetingNotesDraftListQuery
from src.modules.workspace.application.dto.meeting_notes_draft_dto import MeetingNotesDraftResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    MeetingNotesDraftSummaryResult,
)
from src.modules.workspace.application.mappers.meeting_notes_draft_mapper import (
    MeetingNotesDraftMapper,
)
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting._support import load_meeting
from src.modules.workspace.application.use_cases.meeting._support import meeting_result
from src.modules.workspace.application.use_cases.meeting._support import queue_notifications
from src.modules.workspace.application.use_cases.meeting._support import record
from src.modules.workspace.application.use_cases.meeting._support import resolve_attendees
from src.modules.workspace.application.use_cases.meeting._support import resolve_todo_owners
from src.modules.workspace.application.use_cases.meeting._support import save_card_content
from src.modules.workspace.application.use_cases.meeting.meetings import apply_meeting_fields
from src.modules.workspace.application.use_cases.meeting.meetings import assert_owner_open
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftAttendee
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftCard
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNewMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNextMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftTodo
from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.services.meeting_notes_draft_rules import CARDS_MAX
from src.modules.workspace.domain.services.meeting_notes_draft_rules import MeetingNotesDraftRules
from src.modules.workspace.domain.services.meeting_rules import ATTENDEES_MAX
from src.modules.workspace.domain.services.meeting_rules import DECISION_MAX
from src.modules.workspace.domain.services.meeting_rules import LOCATION_MAX
from src.modules.workspace.domain.services.meeting_rules import TODO_NOTE_MAX
from src.modules.workspace.domain.services.meeting_rules import TODO_TITLE_MAX
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.services.person_name_matching import PersonCandidate
from src.modules.workspace.domain.services.person_name_matching import PersonKind
from src.modules.workspace.domain.services.person_name_matching import PersonMatch
from src.modules.workspace.domain.services.person_name_matching import match_person
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_notes_draft_repository import (
    IMeetingNotesDraftRepository,
)
from src.shared_kernel.domain.services.clock import now_utc

# The users a draft's names are matched against are read in one page.
_USERS_MAX = 2_000


@dataclass(frozen=True)
class NotesDraftPorts:
    meeting: MeetingPorts
    drafts: IMeetingNotesDraftRepository
    links: IContactLinkRepository
    users: IUserRepository


class _NotesDraftUseCase:
    def __init__(self, ports: NotesDraftPorts) -> None:
        self._ports = ports
        self._drafts = ports.drafts

    async def _load(self, actor: User, draft_id: int) -> MeetingNotesDraft:
        return MeetingNotesDraftRules.assert_visible(await self._drafts.get_by_id(draft_id), actor)


# ── Submit ────────────────────────────────────────────────────────────


def _draft_cards(cmd: CreateMeetingNotesDraftCommand) -> list[DraftCard]:
    return [
        DraftCard(
            scope=card.scope,
            scope_icon=card.scope_icon,
            body=card.body,
            internal=card.internal,
            decisions=list(card.decisions),
            todos=[
                DraftTodo(title=t.title, note=t.note, due_date=t.due_date, owners=list(t.owners))
                for t in card.todos
            ],
            review_note=card.review_note,
        )
        for card in cmd.cards
    ]


class CreateMeetingNotesDraft(_NotesDraftUseCase):
    async def execute(
        self, actor: User, cmd: CreateMeetingNotesDraftCommand
    ) -> MeetingNotesDraftSummaryResult:
        MeetingRules.assert_can_write(actor)
        MeetingNotesDraftRules.assert_target(cmd.meeting_id, cmd.project_id, cmd.product_id)
        meeting_ports = self._ports.meeting
        new_meeting: DraftNewMeeting | None = None
        if cmd.meeting_id is not None:
            if cmd.new_meeting is not None:
                raise MeetingInvalidInputError(
                    "A draft that adds to a meeting cannot also propose a new one."
                )
            MeetingRules.assert_editable(await load_meeting(meeting_ports, cmd.meeting_id))
        else:
            if cmd.new_meeting is None:
                raise MeetingInvalidInputError(
                    "A draft of a new meeting needs its name, start and end."
                )
            await assert_owner_open(meeting_ports, cmd.project_id, cmd.product_id)
            new_meeting = MeetingNotesDraftRules.new_meeting(
                DraftNewMeeting(**cmd.new_meeting.model_dump())
            )
        if cmd.next_meeting_time is not None and cmd.next_meeting_date is None:
            raise MeetingInvalidInputError("The next meeting's time needs its date.")
        next_meeting = (
            DraftNextMeeting(
                day=cmd.next_meeting_date,
                start_time=cmd.next_meeting_time,
                location=cmd.next_meeting_location,
            )
            if cmd.next_meeting_date is not None
            else None
        )
        draft = MeetingNotesDraft(
            id=0,
            creator_id=actor.id,
            created=now_utc(),
            meeting_id=cmd.meeting_id,
            project_id=cmd.project_id,
            product_id=cmd.product_id,
            new_meeting=new_meeting,
            attendees=MeetingNotesDraftRules.attendees(
                [DraftAttendee(name=a.name, status=a.status, email=a.email) for a in cmd.attendees]
            ),
            cards=MeetingNotesDraftRules.cards(_draft_cards(cmd)),
            next_meeting=MeetingNotesDraftRules.next_meeting(next_meeting),
            review_note=MeetingNotesDraftRules.review_note(cmd.review_note),
            token_name=cmd.token_name,
        )
        saved = await self._drafts.save(draft)
        await meeting_ports.uow.commit()
        log.info(f"Created meeting notes draft #{saved.id} for user #{actor.id}.")
        return MeetingNotesDraftMapper.summary(saved)


# ── Read ──────────────────────────────────────────────────────────────


class ListMeetingNotesDrafts(_NotesDraftUseCase):
    async def execute(
        self, actor: User, query: MeetingNotesDraftListQuery
    ) -> list[MeetingNotesDraftSummaryResult]:
        drafts = await self._drafts.get_by_creator(
            actor.id,
            meeting_id=query.meeting_id,
            project_id=query.project_id,
            product_id=query.product_id,
        )
        return [MeetingNotesDraftMapper.summary(d) for d in drafts]


class GetMeetingNotesDraft(_NotesDraftUseCase):
    async def execute(self, actor: User, draft_id: int) -> MeetingNotesDraftResult:
        draft = await self._load(actor, draft_id)
        candidates = await self._candidates(actor, draft)
        names = [a.name for a in draft.attendees] + [
            owner for card in draft.cards for todo in card.todos for owner in todo.owners
        ]
        matches: list[PersonMatch] = [
            match_person(name, candidates) for name in dict.fromkeys(names)
        ]
        return MeetingNotesDraftMapper.detail(draft, matches)

    async def _candidates(self, actor: User, draft: MeetingNotesDraft) -> list[PersonCandidate]:
        _, users = await self._ports.users.get_multi(
            UserFilterDto(limit=_USERS_MAX, is_active=True, is_service_account=False)
        )
        found = [
            PersonCandidate(kind=PersonKind.USER, id=u.id, name=u.full_name, aliases=(u.username,))
            for u in users
            if not u.is_systemuser
        ]
        if not actor.has_permission(Permission.READ_CONTACTS):
            return found
        contact_ids = await self._contact_ids(draft)
        contacts = await self._ports.meeting.contacts.get_by_ids(sorted(contact_ids))
        found += [
            PersonCandidate(kind=PersonKind.CONTACT, id=c.id, name=c.name, email=c.email)
            for c in contacts
            if not c.archived
        ]
        return found

    async def _contact_ids(self, draft: MeetingNotesDraft) -> set[int]:
        """The contacts linked to the meeting's owner and those already on
        the meeting."""
        ports = self._ports.meeting
        ids: set[int] = set()
        project_id, product_id = draft.project_id, draft.product_id
        if draft.meeting_id is not None:
            meeting = await load_meeting(ports, draft.meeting_id)
            project_id, product_id = meeting.project_id, meeting.product_id
            ids |= {a.contact_id for a in meeting.attendees if a.contact_id is not None}
        if project_id is not None:
            project = await ports.projects.get_by_id(project_id)
            if project is None:
                return ids
            product_links = (
                await self._ports.links.get_links(ContactLinkOwner.PRODUCT, project.product_id)
                if project.product_id is not None
                else []
            )
            project_links = await self._ports.links.get_links(ContactLinkOwner.PROJECT, project.id)
            ids |= {
                entry.contact_id
                for entry in ContactLinkRules.resolve_project_contacts(product_links, project_links)
            }
        elif product_id is not None:
            links = await self._ports.links.get_links(ContactLinkOwner.PRODUCT, product_id)
            ids |= {link.contact_id for link in links}
        return ids


# ── Apply and discard ─────────────────────────────────────────────────


class ApplyMeetingNotesDraft(_NotesDraftUseCase):
    async def execute(
        self, actor: User, draft_id: int, cmd: ApplyMeetingNotesDraftCommand
    ) -> ApplyMeetingNotesDraftResult:
        MeetingRules.assert_can_write(actor)
        draft = await self._load(actor, draft_id)
        if not cmd.cards:
            raise MeetingInvalidInputError("Applying a draft needs at least one card.")
        if len(cmd.cards) > CARDS_MAX:
            raise MeetingInvalidInputError(f"A draft has at most {CARDS_MAX} cards.")
        ports = self._ports.meeting
        if draft.meeting_id is not None:
            meeting = await self._existing_meeting(draft.meeting_id, cmd)
        else:
            meeting = await self._new_meeting(actor, draft, cmd)

        assigned: dict[int, int] = {}
        decision_count = todo_count = 0
        for card_input in cmd.cards:
            card = MeetingCard(
                id=0,
                meeting_id=meeting.id,
                position=await ports.cards.next_position(meeting.id),
                scope=None,
                scope_icon=None,
                body="",
                internal=False,
                created=now_utc(),
                creator_id=actor.id,
            )
            saved = (
                await save_card_content(
                    ports,
                    actor,
                    card,
                    scope=card_input.scope,
                    scope_icon=card_input.scope_icon,
                    body=card_input.body,
                    internal=card_input.internal,
                    always_new_revision=True,
                )
            ).card
            for text in card_input.decisions:
                await ports.cards.save_decision(
                    MeetingDecision(
                        id=0,
                        meeting_id=meeting.id,
                        card_id=saved.id,
                        position=await ports.cards.next_decision_position(saved.id),
                        text=MeetingRules.required_text(text, "decision", DECISION_MAX),
                        created=now_utc(),
                        creator_id=actor.id,
                    )
                )
                decision_count += 1
            for todo_input in card_input.todos:
                todo = MeetingTodo(
                    id=0,
                    meeting_id=meeting.id,
                    card_id=saved.id,
                    position=await ports.cards.next_todo_position(saved.id),
                    title=MeetingRules.required_text(
                        todo_input.title, "todo's title", TODO_TITLE_MAX
                    ),
                    note=MeetingRules.optional_text(todo_input.note, "todo's note", TODO_NOTE_MAX),
                    due_date=todo_input.due_date,
                    created=now_utc(),
                    creator_id=actor.id,
                )
                todo.owners = await resolve_todo_owners(ports, todo_input.owners, [])
                saved_todo = await ports.cards.save_todo(todo)
                for user_id in saved_todo.owner_user_ids:
                    assigned[user_id] = assigned.get(user_id, 0) + 1
                todo_count += 1

        await queue_notifications(ports, meeting.id, actor, todos=assigned)
        await record(
            ports,
            meeting.id,
            MeetingEventKind.IMPORTED,
            actor,
            summary=draft.token_name,
            details={
                "cards": len(cmd.cards),
                "decisions": decision_count,
                "todos": todo_count,
                "draft": str(draft.public_id),
            },
        )
        await self._drafts.delete(draft)
        await ports.uow.commit()
        log.info(
            f"Applied meeting notes draft #{draft.id} to meeting {meeting.meeting_number} "
            f"(ID={meeting.id}): {len(cmd.cards)} card(s)."
        )
        return ApplyMeetingNotesDraftResult(meeting=await meeting_result(ports, meeting))

    async def _existing_meeting(
        self, meeting_id: int, cmd: ApplyMeetingNotesDraftCommand
    ) -> Meeting:
        """Adds the attendees the form lists that are not on the meeting yet,
        and the next meeting when the meeting has none."""
        if cmd.new_meeting is not None:
            raise MeetingInvalidInputError(
                "A draft that adds to a meeting cannot also create a new one."
            )
        ports = self._ports.meeting
        meeting = await load_meeting(ports, meeting_id)
        MeetingRules.assert_editable(meeting)
        resolved = await resolve_attendees(ports, _distinct(cmd.attendees), meeting.attendees)
        added = [a for a in resolved if a.id == 0]
        if len(meeting.attendees) + len(added) > ATTENDEES_MAX:
            raise MeetingInvalidInputError(f"A meeting has at most {ATTENDEES_MAX} attendees.")
        start = len(meeting.attendees)
        for offset, attendee in enumerate(added):
            attendee.position = start + offset
        meeting.attendees = [*meeting.attendees, *added]
        touched = bool(added)
        if meeting.next_meeting_date is None and cmd.next_meeting_date is not None:
            meeting.next_meeting_date = cmd.next_meeting_date
            meeting.next_meeting_time = cmd.next_meeting_time
            meeting.next_meeting_location = MeetingRules.optional_text(
                cmd.next_meeting_location, "next meeting's place", LOCATION_MAX
            )
            touched = True
        if not touched:
            return meeting
        meeting.changed = now_utc()
        return await ports.meetings.save(meeting)

    async def _new_meeting(
        self, actor: User, draft: MeetingNotesDraft, cmd: ApplyMeetingNotesDraftCommand
    ) -> Meeting:
        if cmd.new_meeting is None:
            raise MeetingInvalidInputError("A new meeting needs its name, start and end.")
        ports = self._ports.meeting
        await assert_owner_open(ports, draft.project_id, draft.product_id)
        fields = CreateMeetingCommand(
            name=cmd.new_meeting.name,
            starts_at=cmd.new_meeting.starts_at,
            ends_at=cmd.new_meeting.ends_at,
            location=cmd.new_meeting.location,
            next_meeting_date=cmd.next_meeting_date,
            next_meeting_time=cmd.next_meeting_time,
            next_meeting_location=cmd.next_meeting_location,
            tags=list(cmd.new_meeting.tags),
            project_id=draft.project_id,
            product_id=draft.product_id,
        )
        meeting = Meeting(
            id=0,
            meeting_number="",
            name="",
            starts_at=fields.starts_at,
            ends_at=fields.ends_at,
            created=now_utc(),
            creator_id=actor.id,
            project_id=draft.project_id,
            product_id=draft.product_id,
        )
        apply_meeting_fields(meeting, fields)
        meeting.attendees = await resolve_attendees(ports, _distinct(cmd.attendees), [])
        template = (await ports.settings.get_made_items()).meeting_number_format
        # The number is drawn last, after every other read of the meeting.
        meeting.meeting_number = await ports.meetings.next_number(template)
        saved = await ports.meetings.save(meeting)
        await record(ports, saved.id, MeetingEventKind.CREATED, actor, at=saved.created)
        return saved


def _distinct(inputs: list[MeetingAttendeeInput]) -> list[MeetingAttendeeInput]:
    """The attendees without a second entry for the same user or contact,
    which two spellings of one name in the notes can lead to."""
    seen: set[tuple[MeetingAttendeeKind, int]] = set()
    result: list[MeetingAttendeeInput] = []
    for item in inputs:
        ref = item.user_id if item.kind == MeetingAttendeeKind.USER else item.contact_id
        if item.kind != MeetingAttendeeKind.GUEST and ref is not None:
            if (item.kind, ref) in seen:
                continue
            seen.add((item.kind, ref))
        result.append(item)
    return result


class DiscardMeetingNotesDraft(_NotesDraftUseCase):
    async def execute(self, actor: User, draft_id: int) -> None:
        draft = await self._load(actor, draft_id)
        await self._drafts.delete(draft)
        await self._ports.meeting.uow.commit()
        log.info(f"Discarded meeting notes draft #{draft.id}.")


class PurgeExpiredMeetingNotesDrafts:
    """Deletes the drafts nobody applied or discarded within their
    retention, since they keep the names of people."""

    def __init__(self, drafts: IMeetingNotesDraftRepository, uow: IUnitOfWork) -> None:
        self._drafts = drafts
        self._uow = uow

    async def execute(self) -> int:
        removed = await self._drafts.delete_created_before(
            MeetingNotesDraftRules.expired_before(now_utc())
        )
        await self._uow.commit()
        if removed:
            log.info(f"Deleted {removed} meeting notes draft(s) past their retention.")
        return removed
