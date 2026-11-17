"""
What the meeting use cases share: the ports they work with, loading a
meeting and its rows, the history, building the results, checking
attendees and todo owners, saving a card's text with its revision and
mentions, and queueing the notifications of mentions and assignments.
"""

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import tzinfo

from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.ports.outbound.catalogue_queries import IContactQueries
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.meeting_dto import MeetingAttendeeInput
from src.modules.workspace.application.dto.meeting_dto import MeetingCardResult
from src.modules.workspace.application.dto.meeting_dto import MeetingFileResult
from src.modules.workspace.application.dto.meeting_dto import MeetingResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoOwnerInput
from src.modules.workspace.application.mappers.meeting_mapper import MeetingMapper
from src.modules.workspace.application.mappers.meeting_mapper import card_user_ids
from src.modules.workspace.application.mappers.meeting_mapper import meeting_user_ids
from src.modules.workspace.application.use_cases.meeting._file_kind import MEETING_FILE_KIND
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingAttendee
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingCardMention
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingEvent
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting import MeetingTodoOwner
from src.modules.workspace.domain.errors import MeetingCardNotFoundError
from src.modules.workspace.domain.errors import MeetingDecisionNotFoundError
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingNotFoundError
from src.modules.workspace.domain.errors import MeetingTodoNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.services.meeting_markdown import normalise_card_markdown
from src.modules.workspace.domain.services.meeting_markdown import referenced_ids
from src.modules.workspace.domain.services.meeting_rules import ATTENDEES_MAX
from src.modules.workspace.domain.services.meeting_rules import SCOPE_MAX
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import IMeetingNotesJournal
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingCardRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingNotificationQueue,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import IMeetingRepository
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingSnapshotRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class MeetingPorts:
    """The ports every meeting use case may need, built once per request."""

    meetings: IMeetingRepository
    cards: IMeetingCardRepository
    files: IMeetingFileRepository
    queue: IMeetingNotificationQueue
    projects: IProjectRepository
    products: IProductRepository
    contacts: IContactQueries
    # The made-item settings carry the meeting number format.
    settings: ICatalogueSettingsRepository
    storage: IStoragePort | None
    uow: IUnitOfWork
    # The snapshots and the export journal of printed, downloaded and sent
    # notes, which only the distribution and anonymisation need.
    snapshots: IMeetingSnapshotRepository | None = None
    journal: IMeetingNotesJournal | None = None

    async def zone(self) -> tzinfo:
        return await tenant_zone(self.settings)


class MeetingUseCase:
    def __init__(self, ports: MeetingPorts) -> None:
        self._ports = ports
        self._meetings = ports.meetings
        self._cards = ports.cards
        self._uow = ports.uow


# ── Loading ───────────────────────────────────────────────────────────


async def load_meeting(ports: MeetingPorts, meeting_id: int) -> Meeting:
    meeting = await ports.meetings.get_by_id(meeting_id)
    if meeting is None or meeting.deleted:
        raise MeetingNotFoundError(f"Meeting #{meeting_id} not found.")
    return meeting


async def load_card(ports: MeetingPorts, meeting: Meeting, card_id: int) -> MeetingCard:
    card = await ports.cards.get_card(card_id)
    if card is None or card.meeting_id != meeting.id:
        raise MeetingCardNotFoundError(f"Card #{card_id} not found.")
    return card


async def load_todo(ports: MeetingPorts, meeting: Meeting, todo_id: int) -> MeetingTodo:
    todo = await ports.cards.get_todo(todo_id)
    if todo is None or todo.meeting_id != meeting.id:
        raise MeetingTodoNotFoundError(f"Todo #{todo_id} not found.")
    return todo


async def load_decision(ports: MeetingPorts, meeting: Meeting, decision_id: int) -> MeetingDecision:
    decision = await ports.cards.get_decision(decision_id)
    if decision is None or decision.meeting_id != meeting.id:
        raise MeetingDecisionNotFoundError(f"Decision #{decision_id} not found.")
    return decision


async def owner_meetings_scope(
    ports: MeetingPorts, project_id: int | None, product_id: int | None, *, with_projects: bool
) -> tuple[list[int], list[int]]:
    """The projects and products whose meetings an owner's list or scopes
    cover: a project alone, or a product with each of its projects when
    asked."""
    MeetingRules.assert_owner(project_id, product_id)
    if project_id is not None:
        project = await ports.projects.get_by_id(project_id)
        if project is None or project.deleted:
            raise ProjectNotFoundError(f"Project #{project_id} not found.")
        return [project_id], []
    assert product_id is not None
    if await ports.products.get_by_id(product_id) is None:
        raise ProductNotFoundError(f"Product #{product_id} not found.")
    projects = await ports.projects.get_by_product_id(product_id) if with_projects else []
    return [p.id for p in projects if not p.deleted], [product_id]


# ── History ───────────────────────────────────────────────────────────


async def record(
    ports: MeetingPorts,
    meeting_id: int,
    kind: MeetingEventKind,
    actor: User | None,
    *,
    at: datetime | None = None,
    card_id: int | None = None,
    todo_id: int | None = None,
    file_id: int | None = None,
    summary: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    await ports.meetings.add_event(
        MeetingEvent(
            id=0,
            meeting_id=meeting_id,
            kind=kind,
            at=at or now_utc(),
            actor_id=actor.id if actor is not None else None,
            card_id=card_id,
            todo_id=todo_id,
            file_id=file_id,
            summary=summary,
            details=details,
        )
    )


def card_label(card: MeetingCard) -> str:
    return card.scope or "No scope"


# ── Results ───────────────────────────────────────────────────────────


def file_result(storage: IStoragePort | None, file: MeetingFile) -> MeetingFileResult:
    """The file's result with the card a pasted image belongs to, which the
    shared attachment shape does not carry."""
    result = MEETING_FILE_KIND.to_result(file, storage)
    return result.model_copy(update={"card_id": file.card_id})


async def card_results(
    ports: MeetingPorts, meeting_id: int, cards: list[MeetingCard] | None = None
) -> list[MeetingCardResult]:
    cards = cards if cards is not None else await ports.cards.get_cards(meeting_id)
    decisions = await ports.cards.get_decisions(meeting_id)
    todos = await ports.cards.get_todos(meeting_id)
    users = await ports.meetings.get_users(card_user_ids(cards, decisions, todos))
    return [MeetingMapper.card(card, decisions, todos, users) for card in cards]


async def card_result(ports: MeetingPorts, card: MeetingCard) -> MeetingCardResult:
    return (await card_results(ports, card.meeting_id, [card]))[0]


async def meeting_result(ports: MeetingPorts, meeting: Meeting) -> MeetingResult:
    users = await ports.meetings.get_users(meeting_user_ids(meeting))
    follow_up_of = (
        await ports.meetings.get_by_id(meeting.follow_up_of_id)
        if meeting.follow_up_of_id is not None
        else None
    )
    files = [file_result(ports.storage, f) for f in await ports.files.get_by_item_id(meeting.id)]
    return MeetingMapper.meeting(
        meeting,
        follow_up_of=follow_up_of,
        cards=await card_results(ports, meeting.id),
        files=files,
        users=users,
    )


# ── Attendees and owners ──────────────────────────────────────────────


# Says an attendee is listed twice: its kind and its user, contact or row.
_AttendeeKey = tuple[str, int]


async def resolve_attendees(
    ports: MeetingPorts, inputs: list[MeetingAttendeeInput], existing: list[MeetingAttendee]
) -> list[MeetingAttendee]:
    """The attendees as the request lists them. Users must exist, contacts
    must exist and, when new to the meeting, not be archived, and a guest
    needs a name. A user or contact already on the meeting keeps its row,
    and a contact keeps the copy of its name and address."""
    if len(inputs) > ATTENDEES_MAX:
        raise MeetingInvalidInputError(f"A meeting has at most {ATTENDEES_MAX} attendees.")
    by_user = {a.user_id: a for a in existing if a.user_id is not None}
    by_contact = {a.contact_id: a for a in existing if a.contact_id is not None}
    by_id = {a.id: a for a in existing}
    user_ids = {i.user_id for i in inputs if i.kind == MeetingAttendeeKind.USER and i.user_id}
    users = await ports.meetings.get_users(user_ids)
    contact_ids = [
        i.contact_id
        for i in inputs
        if i.kind == MeetingAttendeeKind.CONTACT and i.contact_id is not None
    ]
    contacts = {c.id: c for c in await ports.contacts.get_by_ids(contact_ids)}

    seen: set[_AttendeeKey] = set()
    result: list[MeetingAttendee] = []
    for position, item in enumerate(inputs):
        if item.kind == MeetingAttendeeKind.USER:
            key, attendee = _user_attendee(item, users, by_user)
        elif item.kind == MeetingAttendeeKind.CONTACT:
            key, attendee = _contact_attendee(item, contacts, by_contact)
        else:
            key, attendee = _guest_attendee(item, position, by_id)
        if key in seen:
            raise MeetingInvalidInputError("An attendee is listed twice.")
        seen.add(key)
        result.append(replace(attendee, status=item.status, position=position))
    return result


def _user_attendee(
    item: MeetingAttendeeInput, users: dict[int, User], by_user: dict[int, MeetingAttendee]
) -> tuple[_AttendeeKey, MeetingAttendee]:
    if item.user_id is None or item.user_id not in users:
        raise MeetingInvalidInputError(f"User #{item.user_id} not found.")
    attendee = by_user.get(item.user_id) or MeetingAttendee(
        id=0, kind=item.kind, status=item.status, user_id=item.user_id
    )
    return ("user", item.user_id), attendee


def _contact_attendee(
    item: MeetingAttendeeInput,
    contacts: dict[int, Contact],
    by_contact: dict[int, MeetingAttendee],
) -> tuple[_AttendeeKey, MeetingAttendee]:
    """A contact new to the meeting must not be archived; one already on it
    keeps its row and the copy of its name and address."""
    contact = contacts.get(item.contact_id) if item.contact_id is not None else None
    if contact is None or item.contact_id is None:
        raise MeetingInvalidInputError(f"Contact #{item.contact_id} not found.")
    known = by_contact.get(item.contact_id)
    if known is None and contact.archived:
        raise MeetingInvalidInputError(f"Contact #{item.contact_id} is archived.")
    attendee = known or MeetingAttendee(
        id=0,
        kind=item.kind,
        status=item.status,
        contact_id=contact.id,
        name=contact.name,
        email=contact.email,
    )
    return ("contact", item.contact_id), attendee


def _guest_attendee(
    item: MeetingAttendeeInput, position: int, by_id: dict[int, MeetingAttendee]
) -> tuple[_AttendeeKey, MeetingAttendee]:
    """A guest needs a name. One already on the meeting keeps its row, and
    an anonymised one keeps its blanked name and address."""
    name = MeetingRules.required_text(item.name or "", "guest's name", 200)
    email = MeetingRules.optional_text(item.email, "guest's e-mail address", 320)
    known = by_id.get(item.attendee_id) if item.attendee_id is not None else None
    if known is not None and known.kind != MeetingAttendeeKind.GUEST:
        known = None
    key = ("guest", known.id if known is not None else -position - 1)
    attendee = known or MeetingAttendee(id=0, kind=item.kind, status=item.status)
    if attendee.anonymised_at is None:
        attendee.name = name
        attendee.email = email
    return key, attendee


async def resolve_todo_owners(
    ports: MeetingPorts, inputs: list[MeetingTodoOwnerInput], existing: list[MeetingTodoOwner]
) -> list[MeetingTodoOwner]:
    """The owners of a todo: users that exist and contacts that exist. A
    contact new to the todo must not be archived and leaves a copy of its
    name; one the todo had keeps its copy."""
    for item in inputs:
        if (item.user_id is None) == (item.contact_id is None):
            raise MeetingInvalidInputError("A todo owner is either a user or a contact.")
    users = await ports.meetings.get_users({i.user_id for i in inputs if i.user_id is not None})
    contact_ids = [i.contact_id for i in inputs if i.contact_id is not None]
    contacts = {c.id: c for c in await ports.contacts.get_by_ids(contact_ids)}
    known = {o.contact_id: o for o in existing if o.contact_id is not None}
    owners: list[MeetingTodoOwner] = []
    seen: set[tuple[int | None, int | None]] = set()
    for item in inputs:
        key = (item.user_id, item.contact_id)
        if key in seen:
            continue
        seen.add(key)
        if item.user_id is not None:
            if item.user_id not in users:
                raise MeetingInvalidInputError(f"User #{item.user_id} not found.")
            owners.append(MeetingTodoOwner(id=0, user_id=item.user_id))
            continue
        assert item.contact_id is not None
        if item.contact_id in known:
            owners.append(known[item.contact_id])
            continue
        contact = contacts.get(item.contact_id)
        if contact is None:
            raise MeetingInvalidInputError(f"Contact #{item.contact_id} not found.")
        if contact.archived:
            raise MeetingInvalidInputError(f"Contact #{item.contact_id} is archived.")
        owners.append(MeetingTodoOwner(id=0, contact_id=contact.id, name=contact.name))
    return owners


# ── Cards ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SavedCard:
    card: MeetingCard
    # Whether the save started a revision rather than updating the last.
    new_revision: bool


async def save_card_content(
    ports: MeetingPorts,
    actor: User,
    card: MeetingCard,
    *,
    scope: str | None,
    scope_icon: MeetingScopeIcon | None,
    body: str,
    internal: bool,
    always_new_revision: bool = False,
) -> SavedCard:
    """Writes the card's scope, icon, text and internal flag with the text
    in canonical form, its revision and its mentions, and queues the
    notifications of users it newly mentions."""
    MeetingRules.assert_body(body)
    now = now_utc()
    candidate_users, candidate_files = referenced_ids(body)
    users = await ports.meetings.get_users(candidate_users)
    files = {
        f.id for f in await ports.files.get_by_item_id(card.meeting_id) if f.id in candidate_files
    }
    normalised = normalise_card_markdown(body, user_ids=set(users), file_ids=files)

    card.scope = MeetingRules.optional_text(scope, "scope", SCOPE_MAX)
    card.scope_icon = scope_icon
    card.body = normalised.text
    card.internal = internal
    if card.id != 0:
        card.changed = now
    saved = await ports.cards.save_card(card)

    last = await ports.cards.last_revision(saved.id)
    merge = not always_new_revision and MeetingRules.merges_into(last, actor.id, now)
    if merge and last is not None:
        last.scope, last.scope_icon = saved.scope, saved.scope_icon
        last.body, last.internal, last.saved_at = saved.body, saved.internal, now
        await ports.cards.save_revision(last)
    else:
        await ports.cards.save_revision(
            MeetingCardRevision(
                id=0,
                card_id=saved.id,
                scope=saved.scope,
                scope_icon=saved.scope_icon,
                body=saved.body,
                internal=saved.internal,
                author_id=actor.id,
                created=now,
                saved_at=now,
            )
        )

    mentions = {m.user_id: m for m in await ports.cards.get_mentions(saved.id)}
    newly_mentioned: set[int] = set()
    for user_id in normalised.mentioned_user_ids:
        mention = mentions.get(user_id)
        if mention is None:
            await ports.cards.save_mention(
                MeetingCardMention(
                    id=0, card_id=saved.id, user_id=user_id, present=True, created=now
                )
            )
            newly_mentioned.add(user_id)
        elif not mention.present:
            mention.present = True
            await ports.cards.save_mention(mention)
    for user_id, mention in mentions.items():
        if mention.present and user_id not in normalised.mentioned_user_ids:
            mention.present = False
            await ports.cards.save_mention(mention)
    await queue_notifications(
        ports, saved.meeting_id, actor, mentions={u: 1 for u in newly_mentioned}
    )
    return SavedCard(card=saved, new_revision=not merge)


async def queue_notifications(
    ports: MeetingPorts,
    meeting_id: int,
    actor: User,
    *,
    mentions: dict[int, int] | None = None,
    todos: dict[int, int] | None = None,
) -> None:
    """Adds mentions and todo assignments per recipient to what waits to go
    out for the meeting. Nobody is notified of their own actions, and only
    active users are notified at all."""
    mentions = mentions or {}
    todos = todos or {}
    recipients = (set(mentions) | set(todos)) - {actor.id}
    if not recipients:
        return
    users = await ports.meetings.get_users(recipients)
    now = now_utc()
    for recipient in sorted(recipients):
        user = users.get(recipient)
        if user is None or not user.is_active:
            continue
        await ports.queue.add(
            meeting_id=meeting_id,
            recipient_id=recipient,
            actor_id=actor.id,
            mentions=mentions.get(recipient, 0),
            todos=todos.get(recipient, 0),
            now=now,
        )
