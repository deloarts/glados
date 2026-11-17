"""
Read scenarios of contacts and meetings: the contacts of customers and
suppliers, their links to products and projects, and a meeting with its
cards, files, waiting notifications and snapshots, and the meeting notes
drafts an agent proposes. See the package docstring for how the scenarios
work.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.contact_repository import (
    SqlAlchemyContactRepository,
)
from src.modules.catalogue.ports.outbound.repositories.contact_repository import ContactFilterDto
from src.modules.workspace.adapters.outbound.persistence.repositories.contact_link_repository import (
    SqlAlchemyContactLinkRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_card_repository import (
    SqlAlchemyMeetingCardRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_file_repository import (
    SqlAlchemyMeetingFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notes_draft_repository import (
    SqlAlchemyMeetingNotesDraftRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notification_queue import (
    SqlAlchemyMeetingNotificationQueue,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_repository import (
    SqlAlchemyMeetingRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_snapshot_repository import (
    SqlAlchemyMeetingSnapshotRepository,
)
from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingCardMention
from src.modules.workspace.domain.entities.meeting import MeetingCardRevision
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingEvent
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting import MeetingTodoOwner
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftCard
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNewMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotAttendee
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotFacts
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import TODAY
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import file_fields
from tests.integration.repository_reads._graph import make
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()

_SCOPE = "Gripper 1"


async def _card_with_todo(g: Graph) -> tuple[MeetingCard, MeetingTodo]:
    """A card of the meeting with a revision, a mention, a decision and an
    open todo due today that a user and the customer's contact own."""
    meeting = await g.meeting()
    contact = await g.customer_contact()
    cards = SqlAlchemyMeetingCardRepository(g.db)
    card = await cards.save_card(
        make(
            MeetingCard,
            meeting_id=meeting.id,
            position=0,
            scope=_SCOPE,
            scope_icon=MeetingScopeIcon.MECHANICS,
            body="The gripper needs a second sensor.",
            created=NOW,
            creator_id=g.uid,
        )
    )
    await cards.save_revision(
        make(
            MeetingCardRevision,
            card_id=card.id,
            scope=_SCOPE,
            scope_icon=MeetingScopeIcon.MECHANICS,
            body=card.body,
            author_id=g.uid,
            created=NOW,
            saved_at=NOW,
        )
    )
    await cards.save_mention(
        make(MeetingCardMention, card_id=card.id, user_id=g.other_user.id, present=True)
    )
    await cards.save_decision(
        make(
            MeetingDecision,
            meeting_id=meeting.id,
            card_id=card.id,
            position=0,
            text="Order the sensor",
            created=NOW,
            creator_id=g.uid,
        )
    )
    todo = await cards.save_todo(
        MeetingTodo(
            id=0,
            meeting_id=meeting.id,
            card_id=card.id,
            position=0,
            title="Order the sensor",
            created=NOW,
            creator_id=g.uid,
            due_date=TODAY,
            owners=[
                MeetingTodoOwner(id=0, user_id=g.uid),
                MeetingTodoOwner(id=0, contact_id=contact.id, name=contact.name),
            ],
        )
    )
    await g.db.commit()
    return card, todo


@SCENARIOS.register(SqlAlchemyContactRepository)
async def _contacts(g: Graph, r: Any) -> None:
    customer_contact = await g.customer_contact()
    supplier_contact = await g.supplier_contact()
    await r.get_by_id(customer_contact.id)
    await r.get_by_ids([customer_contact.id, supplier_contact.id])
    total, _ = await r.get_multi(ContactFilterDto())
    assert total == 2
    assert [c.id for c in await r.get_mail_recipients((await g.supplier()).id)] == [
        supplier_contact.id
    ]
    assert [c.id for c in await r.get_mail_contacts_of_customer((await g.customer()).id)] == [
        customer_contact.id
    ]


@SCENARIOS.register(SqlAlchemyContactLinkRepository)
async def _contact_links(g: Graph, r: Any) -> None:
    contact = await g.customer_contact()
    product = await g.product()
    project = await g.project()
    links = SqlAlchemyContactLinkRepository(g.db)
    for owner, owner_id, receives in (
        (ContactLinkOwner.PRODUCT, product.id, True),
        (ContactLinkOwner.PROJECT, project.id, False),
    ):
        await links.save(
            make(
                ContactLink,
                owner=owner,
                owner_id=owner_id,
                contact_id=contact.id,
                receives_meeting_notes=receives,
                created=NOW,
                creator_id=g.uid,
            )
        )
    await g.db.commit()
    await r.get_links(ContactLinkOwner.PRODUCT, product.id)
    await r.get_links(ContactLinkOwner.PROJECT, project.id)
    await r.get_link(ContactLinkOwner.PROJECT, project.id, contact.id)
    await r.get_usage([contact.id])


@SCENARIOS.register(SqlAlchemyMeetingRepository)
async def _meetings(g: Graph, r: Any) -> None:
    meeting = await g.meeting()
    contact = await g.customer_contact()
    await SqlAlchemyMeetingRepository(g.db).add_event(
        make(MeetingEvent, meeting_id=meeting.id, kind=MeetingEventKind.CREATED, actor_id=g.uid)
    )
    await _card_with_todo(g)
    loaded = await r.get_by_id(meeting.id)
    assert [a.contact_id for a in loaded.attendees if a.contact_id] == [contact.id]
    assert loaded.tags == ["Milestone"]
    await r.get_by_public_id(meeting.public_id)
    assert await r.next_number("MTG-{yy}-{seq:04d}")
    (row,) = await r.list_rows(
        project_ids=[meeting.project_id], product_ids=[], include_invalid=True, today=TODAY
    )
    assert row.open_todo_count == 1
    (tagged,) = await r.list_rows(
        project_ids=[meeting.project_id],
        product_ids=[],
        include_invalid=True,
        today=TODAY,
        tag="milestone",
    )
    assert tagged.meeting.tags == ["Milestone"]
    assert [(use.name, use.count) for use in await r.get_tag_uses()] == [("Milestone", 1)]
    await r.get_users({g.uid, g.other_user.id})
    await r.get_events(meeting.id)
    assert await r.list_started_before(NOW) == [meeting.id]
    await r.get_contact_usage([contact.id])


@SCENARIOS.register(SqlAlchemyMeetingCardRepository)
async def _meeting_cards(g: Graph, r: Any) -> None:
    meeting = await g.meeting()
    card, todo = await _card_with_todo(g)
    await r.get_cards(meeting.id)
    await r.get_card(card.id)
    assert await r.next_position(meeting.id) == 1
    await r.get_cards_with_scope([meeting.id], _SCOPE)
    await r.get_scope_uses([meeting.id])
    revision = await r.last_revision(card.id)
    await r.get_revisions(card.id)
    await r.get_revision(revision.id)
    await r.get_mentions(card.id)
    (decision,) = await r.get_decisions(meeting.id)
    await r.get_decision(decision.id)
    assert await r.next_decision_position(card.id) == 1
    (loaded,) = await r.get_todos(meeting.id)
    assert len(loaded.owners) == 2
    await r.get_todo(todo.id)
    assert await r.next_todo_position(card.id) == 1
    await r.get_open_todos([meeting.id])
    await r.list_open_todos_of_user(g.uid, due_on_or_before=TODAY)


@SCENARIOS.register(SqlAlchemyMeetingFileRepository)
async def _meeting_files(g: Graph, r: Any) -> None:
    meeting = await g.meeting()
    file = await SqlAlchemyMeetingFileRepository(g.db).save(
        make(
            MeetingFile,
            meeting_id=meeting.id,
            category=MeetingFileCategory.PDF,
            uploaded_by_user_id=g.uid,
            **file_fields("meeting"),
        )
    )
    await g.db.commit()
    await r.get_by_id(file.id)
    await r.get_by_item_id(meeting.id)
    await r.get_by_item_id_and_category(meeting.id, MeetingFileCategory.PDF)
    await r.get_by_item_ids([meeting.id])
    assert await r.get_known_storage_paths([file.storage_path, "meetings/gone"]) == {
        file.storage_path
    }


@SCENARIOS.register(SqlAlchemyMeetingNotificationQueue)
async def _meeting_notifications(g: Graph, r: Any) -> None:
    meeting = await g.meeting()
    await SqlAlchemyMeetingNotificationQueue(g.db).add(
        meeting_id=meeting.id,
        recipient_id=g.other_user.id,
        actor_id=g.uid,
        mentions=1,
        todos=1,
        now=NOW - timedelta(minutes=10),
    )
    await g.db.commit()
    (pending,) = await r.get_due(NOW)
    assert (pending.mention_count, pending.todo_count) == (1, 1)


@SCENARIOS.register(SqlAlchemyMeetingSnapshotRepository)
async def _meeting_snapshots(g: Graph, r: Any) -> None:
    meeting = await g.meeting()
    contact = await g.customer_contact()
    assert meeting.project_id is not None
    snapshot = await SqlAlchemyMeetingSnapshotRepository(g.db).save(
        MeetingSnapshot(
            id=0,
            meeting_id=meeting.id,
            journal_entry_id=1,
            kind=MeetingDistributionKind.SENT,
            created=NOW,
            actor_id=g.uid,
            issue_number=1,
            issue_draft=False,
            language="enGB",
            options={},
            byte_size=10,
            sha256="0" * 64,
            facts=SnapshotFacts(
                meeting_number=meeting.meeting_number,
                name=meeting.name,
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=None,
                next_meeting_date=None,
                next_meeting_time=None,
                next_meeting_location=None,
                owner_kind=MeetingOwnerKind.PROJECT,
                owner_id=meeting.project_id,
                owner_number="P-1",
            ),
            attendees=[
                SnapshotAttendee(
                    id=1,
                    kind=MeetingAttendeeKind.CONTACT,
                    status=MeetingAttendanceStatus.DISTRIBUTION_ONLY,
                    position=0,
                    contact_id=contact.id,
                    name=contact.name,
                    email=contact.email,
                )
            ],
            recipients=["anna@example.com"],
        )
    )
    await g.db.commit()
    await r.get_by_id(snapshot.id)
    await r.get_by_meeting(meeting.id)
    await r.last_sent(meeting.id)
    (with_contact,) = await r.get_with_contact(contact.id)
    assert with_contact.attendees[0].name == contact.name


@SCENARIOS.register(SqlAlchemyMeetingNotesDraftRepository)
async def _meeting_notes_drafts(g: Graph, r: Any) -> None:
    """One draft adds to the existing meeting and one proposes a new
    meeting of the product, so both label lookups run."""
    meeting = await g.meeting()
    product = await g.product()
    drafts = SqlAlchemyMeetingNotesDraftRepository(g.db)
    on_meeting = await drafts.save(
        make(
            MeetingNotesDraft,
            creator_id=g.uid,
            created=NOW,
            meeting_id=meeting.id,
            cards=[DraftCard(scope=_SCOPE, scope_icon=None, body="Sensor ordered.")],
        )
    )
    await drafts.save(
        make(
            MeetingNotesDraft,
            creator_id=g.uid,
            created=NOW - timedelta(minutes=1),
            product_id=product.id,
            new_meeting=DraftNewMeeting(
                name="Kick-off",
                starts_at=NOW + timedelta(days=1),
                ends_at=NOW + timedelta(days=1, hours=1),
                location=None,
            ),
        )
    )
    await g.db.commit()
    found = await r.get_by_id(on_meeting.id)
    assert found.meeting_number == meeting.meeting_number
    newest, oldest = await r.get_by_creator(g.uid)
    assert newest.id == on_meeting.id
    assert oldest.owner_number == product.product_number


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
