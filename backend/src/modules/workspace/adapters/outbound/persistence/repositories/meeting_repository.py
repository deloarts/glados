"""
Concrete implementation of IMeetingRepository using SQLAlchemy: meetings
with their attendees and tags, the meeting lists, the tags in use, the
history, the users a meeting names, purging and the copies of contacts.
"""

from collections import defaultdict
from datetime import date
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from src.modules.platform.adapters.outbound.persistence.edit_version_tracking import (
    bump_edit_version_by_hand,
)
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.user_loading import user_load_options
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingAttendeeOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardMentionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardRevisionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingDecisionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingEventOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingFileOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingNotificationOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import MeetingOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTagOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTodoOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTodoOwnerOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_snapshot_model import (
    MeetingSnapshotContactOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_snapshot_model import (
    MeetingSnapshotOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingAttendee
from src.modules.workspace.domain.entities.meeting import MeetingEvent
from src.modules.workspace.domain.services.meeting_tags import TagUse
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    ContactMeetingUsageRow,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import MeetingCardChip
from src.modules.workspace.ports.outbound.repositories.meeting_repository import MeetingListRow


@lru_cache(maxsize=1)
def meeting_load_options() -> tuple[ExecutableOption, ...]:
    return (selectinload(MeetingOrmModel.attendees), selectinload(MeetingOrmModel.tags))


def _attendee_to_entity(orm: MeetingAttendeeOrmModel) -> MeetingAttendee:
    return MeetingAttendee(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        position=orm.position,
        kind=MeetingAttendeeKind(orm.kind),
        status=MeetingAttendanceStatus(orm.status),
        user_id=orm.user_id,
        contact_id=orm.contact_id,
        name=orm.name,
        email=orm.email,
        anonymised_at=utc_aware(orm.anonymised_at),
    )


def meeting_orm_to_entity(
    orm: MeetingOrmModel, owner_number: str = "", owner_product_id: int | None = None
) -> Meeting:
    return Meeting(
        id=orm.id,
        public_id=orm.public_id,
        meeting_number=orm.meeting_number,
        name=orm.name,
        starts_at=utc_aware(orm.starts_at),
        ends_at=utc_aware(orm.ends_at),
        created=utc_aware(orm.created),
        creator_id=orm.creator_id,
        project_id=orm.project_id,
        product_id=orm.product_id,
        location=orm.location,
        next_meeting_date=orm.next_meeting_date,
        next_meeting_time=orm.next_meeting_time,
        next_meeting_location=orm.next_meeting_location,
        follow_up_of_id=orm.follow_up_of_id,
        invalid_at=utc_aware(orm.invalid_at),
        invalid_by_id=orm.invalid_by_id,
        invalid_reason=orm.invalid_reason,
        issue_number=orm.issue_number,
        last_sent_at=utc_aware(orm.last_sent_at),
        last_printed_at=utc_aware(orm.last_printed_at),
        deleted=orm.deleted,
        deleted_at=utc_aware(orm.deleted_at),
        changed=utc_aware(orm.changed),
        changed_by_id=orm.changed_by_id,
        edit_version=orm.edit_version,
        attendees=[_attendee_to_entity(a) for a in orm.attendees],
        tags=[tag.name for tag in orm.tags],
        owner_number=owner_number,
        owner_product_id=owner_product_id,
    )


def _meeting_columns(meeting: Meeting) -> dict[str, Any]:
    return {
        "meeting_number": meeting.meeting_number,
        "project_id": meeting.project_id,
        "product_id": meeting.product_id,
        "name": meeting.name,
        "starts_at": meeting.starts_at,
        "ends_at": meeting.ends_at,
        "location": meeting.location,
        "next_meeting_date": meeting.next_meeting_date,
        "next_meeting_time": meeting.next_meeting_time,
        "next_meeting_location": meeting.next_meeting_location,
        "follow_up_of_id": meeting.follow_up_of_id,
        "invalid_at": meeting.invalid_at,
        "invalid_by_id": meeting.invalid_by_id,
        "invalid_reason": meeting.invalid_reason,
        "issue_number": meeting.issue_number,
        "last_sent_at": meeting.last_sent_at,
        "last_printed_at": meeting.last_printed_at,
        "deleted": meeting.deleted,
        "deleted_at": meeting.deleted_at,
        "created": meeting.created,
        "creator_id": meeting.creator_id,
        "changed": meeting.changed,
    }


def _attendee_columns(attendee: MeetingAttendee, position: int) -> dict[str, Any]:
    return {
        "position": position,
        "kind": attendee.kind.value,
        "user_id": attendee.user_id,
        "contact_id": attendee.contact_id,
        "name": attendee.name,
        "email": attendee.email,
        "status": attendee.status.value,
        "anonymised_at": attendee.anonymised_at,
    }


def _attendees_changed(
    rows: list[MeetingAttendeeOrmModel], attendees: list[MeetingAttendee]
) -> bool:
    """Whether the attendees differ from the stored rows, leaving out when
    one was anonymised. A change of the attendees alone moves the meeting's
    edit version by hand, since the listener only sees the meeting's own
    columns."""
    if len(rows) != len(attendees):
        return True
    for row, (position, attendee) in zip(rows, enumerate(attendees), strict=True):
        wanted = _attendee_columns(attendee, position)
        wanted.pop("anonymised_at")
        if any(getattr(row, key) != value for key, value in wanted.items()):
            return True
    return False


def _event_to_entity(orm: MeetingEventOrmModel) -> MeetingEvent:
    return MeetingEvent(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        kind=MeetingEventKind(orm.kind),
        at=utc_aware(orm.at),
        actor_id=orm.actor_id,
        card_id=orm.card_id,
        todo_id=orm.todo_id,
        file_id=orm.file_id,
        summary=orm.summary,
        details=orm.details,
    )


class SqlAlchemyMeetingRepository:
    """Implements IMeetingRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _owners(self, rows: list[MeetingOrmModel]) -> dict[int, tuple[str, int | None]]:
        """The number of each meeting's owner, and a project's product."""
        project_ids = {r.project_id for r in rows if r.project_id is not None}
        product_ids = {r.product_id for r in rows if r.product_id is not None}
        projects: dict[int, tuple[str, int | None]] = {}
        products: dict[int, str] = {}
        if project_ids:
            result = await self._db.execute(
                select(
                    ProjectOrmModel.id, ProjectOrmModel.project_number, ProjectOrmModel.product_id
                ).where(ProjectOrmModel.id.in_(project_ids))
            )
            projects = {pid: (number, product) for pid, number, product in result.all()}
        if product_ids:
            result = await self._db.execute(
                select(ProductOrmModel.id, ProductOrmModel.product_number).where(
                    ProductOrmModel.id.in_(product_ids)
                )
            )
            products = {pid: number for pid, number in result.all()}
        owners: dict[int, tuple[str, int | None]] = {}
        for row in rows:
            if row.project_id is not None:
                owners[row.id] = projects.get(row.project_id, ("", None))
            elif row.product_id is not None:
                owners[row.id] = (products.get(row.product_id, ""), None)
        return owners

    async def _to_entities(self, rows: list[MeetingOrmModel]) -> list[Meeting]:
        owners = await self._owners(rows)
        return [meeting_orm_to_entity(row, *owners.get(row.id, ("", None))) for row in rows]

    async def _load(self, id: int, *, refresh: bool = False) -> MeetingOrmModel | None:
        stmt = (
            select(MeetingOrmModel).where(MeetingOrmModel.id == id).options(*meeting_load_options())
        )
        if refresh:
            stmt = stmt.execution_options(populate_existing=True)
        orm: MeetingOrmModel | None = await self._db.scalar(stmt)
        return orm

    async def get_by_id(self, id: int) -> Meeting | None:
        orm = await self._load(id)
        if orm is None:
            return None
        return (await self._to_entities([orm]))[0]

    async def get_by_public_id(self, public_id: UUID) -> Meeting | None:
        orm: MeetingOrmModel | None = await self._db.scalar(
            select(MeetingOrmModel)
            .where(MeetingOrmModel.public_id == public_id)
            .options(*meeting_load_options())
        )
        if orm is None:
            return None
        return (await self._to_entities([orm]))[0]

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, MeetingOrmModel, id)

    async def save(self, meeting: Meeting) -> Meeting:
        if meeting.id == 0:
            orm = MeetingOrmModel(**_meeting_columns(meeting))
            orm.attendees = [
                MeetingAttendeeOrmModel(**_attendee_columns(a, i))
                for i, a in enumerate(meeting.attendees)
            ]
            orm.tags = [
                MeetingTagOrmModel(name=name, position=i) for i, name in enumerate(meeting.tags)
            ]
            self._db.add(orm)
        else:
            found = await self._load(meeting.id)
            if found is None:
                raise ValueError(f"MeetingOrmModel id={meeting.id} not found for update.")
            orm = found
            for key, value in _meeting_columns(meeting).items():
                setattr(orm, key, value)
            await self._replace_attendees(orm, meeting.attendees)
            await self._replace_tags(orm, meeting.tags)
        await self._db.flush()
        reloaded = await self._load(orm.id, refresh=True)
        assert reloaded is not None
        return (await self._to_entities([reloaded]))[0]

    async def _replace_attendees(
        self, orm: MeetingOrmModel, attendees: list[MeetingAttendee]
    ) -> None:
        """Updates the rows of the attendees that stay, in their new order,
        and adds the new ones. The rows that leave go in a flush of their
        own, so a person who leaves and comes back in one save meets no
        unique key."""
        if _attendees_changed(orm.attendees, attendees):
            bump_edit_version_by_hand(orm)
        existing = {a.id: a for a in orm.attendees}
        kept: list[MeetingAttendeeOrmModel] = []
        for position, attendee in enumerate(attendees):
            row = existing.get(attendee.id) if attendee.id else None
            if row is None:
                row = MeetingAttendeeOrmModel(**_attendee_columns(attendee, position))
            else:
                for key, value in _attendee_columns(attendee, position).items():
                    setattr(row, key, value)
            kept.append(row)
        if any(row not in kept for row in orm.attendees):
            orm.attendees = [row for row in orm.attendees if row in kept]
            await self._db.flush()
        orm.attendees = kept

    async def _replace_tags(self, orm: MeetingOrmModel, names: list[str]) -> None:
        """Keeps the rows of the tags that stay, renumbered, and adds the new
        ones. The rows that leave go in a flush of their own first, like the
        attendees, so the unique key on the spelling never sees two rows. A
        change of the tags alone moves the meeting's edit version, since the
        listener only sees the meeting's own columns."""
        if [tag.name for tag in orm.tags] != names:
            bump_edit_version_by_hand(orm)
        existing = {tag.name: tag for tag in orm.tags}
        kept: list[MeetingTagOrmModel] = []
        for position, name in enumerate(names):
            row = existing.get(name)
            if row is None:
                row = MeetingTagOrmModel(name=name, position=position)
            else:
                row.position = position
            kept.append(row)
        if any(row not in kept for row in orm.tags):
            orm.tags = [row for row in orm.tags if row in kept]
            await self._db.flush()
        orm.tags = kept

    async def next_number(self, template: str) -> str:
        return await draw_number(
            self._db,
            NumberFamily.MEETING,
            template,
            column=MeetingOrmModel.meeting_number,
        )

    async def list_rows(
        self,
        *,
        project_ids: list[int],
        product_ids: list[int],
        include_invalid: bool,
        today: date,
        tag: str | None = None,
    ) -> list[MeetingListRow]:
        if not project_ids and not product_ids:
            return []
        owner = []
        if project_ids:
            owner.append(MeetingOrmModel.project_id.in_(project_ids))
        if product_ids:
            owner.append(MeetingOrmModel.product_id.in_(product_ids))
        stmt = (
            select(MeetingOrmModel)
            .where(MeetingOrmModel.deleted.is_(False), or_(*owner))
            .options(*meeting_load_options())
            .order_by(MeetingOrmModel.starts_at.desc(), MeetingOrmModel.id.desc())
        )
        if not include_invalid:
            stmt = stmt.where(MeetingOrmModel.invalid_at.is_(None))
        if tag:
            stmt = stmt.where(
                MeetingOrmModel.id.in_(
                    select(MeetingTagOrmModel.meeting_id).where(
                        func.lower(MeetingTagOrmModel.name) == tag.lower()
                    )
                )
            )
        rows = list((await self._db.scalars(stmt)).all())
        if not rows:
            return []
        meetings = await self._to_entities(rows)
        ids = [row.id for row in rows]

        cards: dict[int, list[MeetingCardChip]] = defaultdict(list)
        bodies: dict[int, list[str]] = defaultdict(list)
        card_rows = await self._db.execute(
            select(
                MeetingCardOrmModel.meeting_id,
                MeetingCardOrmModel.scope,
                MeetingCardOrmModel.scope_icon,
                MeetingCardOrmModel.internal,
                MeetingCardOrmModel.body,
            )
            .where(MeetingCardOrmModel.meeting_id.in_(ids))
            .order_by(MeetingCardOrmModel.position, MeetingCardOrmModel.id)
        )
        for meeting_id, scope, icon, internal, body in card_rows.all():
            cards[meeting_id].append(
                MeetingCardChip(
                    scope=scope,
                    icon=MeetingScopeIcon(icon) if icon else None,
                    internal=internal,
                )
            )
            bodies[meeting_id].append(body)

        open_counts: dict[int, tuple[int, int]] = {}
        todo_rows = await self._db.execute(
            select(MeetingTodoOrmModel.meeting_id, MeetingTodoOrmModel.due_date).where(
                MeetingTodoOrmModel.meeting_id.in_(ids), MeetingTodoOrmModel.done_at.is_(None)
            )
        )
        for meeting_id, due in todo_rows.all():
            open_count, overdue = open_counts.get(meeting_id, (0, 0))
            open_counts[meeting_id] = (
                open_count + 1,
                overdue + (1 if due is not None and due < today else 0),
            )
        return [
            MeetingListRow(
                meeting=meeting,
                cards=cards.get(meeting.id, []),
                bodies=bodies.get(meeting.id, []),
                open_todo_count=open_counts.get(meeting.id, (0, 0))[0],
                overdue_todo_count=open_counts.get(meeting.id, (0, 0))[1],
            )
            for meeting in meetings
        ]

    async def get_tag_uses(self) -> list[TagUse]:
        result = await self._db.execute(
            select(MeetingTagOrmModel.name, func.count(MeetingTagOrmModel.meeting_id))
            .join(MeetingOrmModel, MeetingTagOrmModel.meeting_id == MeetingOrmModel.id)
            .where(MeetingOrmModel.deleted.is_(False))
            .group_by(MeetingTagOrmModel.name)
        )
        return [TagUse(name=name, count=count) for name, count in result.all()]

    async def get_users(self, ids: set[int]) -> dict[int, User]:
        if not ids:
            return {}
        rows = await self._db.scalars(
            select(UserOrmModel).where(UserOrmModel.id.in_(ids)).options(*user_load_options())
        )
        return {row.id: user_orm_to_entity(row) for row in rows}

    async def add_event(self, event: MeetingEvent) -> MeetingEvent:
        orm = MeetingEventOrmModel(
            meeting_id=event.meeting_id,
            kind=event.kind.value,
            at=event.at,
            actor_id=event.actor_id,
            card_id=event.card_id,
            todo_id=event.todo_id,
            file_id=event.file_id,
            summary=event.summary,
            details=event.details,
        )
        self._db.add(orm)
        await self._db.flush()
        return _event_to_entity(orm)

    async def get_events(self, meeting_id: int) -> list[MeetingEvent]:
        rows = await self._db.scalars(
            select(MeetingEventOrmModel)
            .where(MeetingEventOrmModel.meeting_id == meeting_id)
            .order_by(MeetingEventOrmModel.at.desc(), MeetingEventOrmModel.id.desc())
        )
        return [_event_to_entity(row) for row in rows]

    async def list_started_before(self, before: datetime) -> list[int]:
        rows = await self._db.scalars(
            select(MeetingOrmModel.id)
            .where(MeetingOrmModel.starts_at < before)
            .order_by(MeetingOrmModel.id)
        )
        return list(rows.all())

    async def purge(self, meeting_id: int) -> None:
        # Other meetings that follow this one keep their row and lose the link.
        await self._db.execute(
            update(MeetingOrmModel)
            .where(MeetingOrmModel.follow_up_of_id == meeting_id)
            .values(follow_up_of_id=None)
        )
        # Every child row goes explicitly, children first, so the purge does
        # not depend on the database enforcing its cascades.
        cards = select(MeetingCardOrmModel.id).where(MeetingCardOrmModel.meeting_id == meeting_id)
        todos = select(MeetingTodoOrmModel.id).where(MeetingTodoOrmModel.meeting_id == meeting_id)
        snapshots = select(MeetingSnapshotOrmModel.id).where(
            MeetingSnapshotOrmModel.meeting_id == meeting_id
        )
        for statement in (
            delete(MeetingSnapshotContactOrmModel).where(
                MeetingSnapshotContactOrmModel.snapshot_id.in_(snapshots)
            ),
            delete(MeetingSnapshotOrmModel).where(MeetingSnapshotOrmModel.meeting_id == meeting_id),
            delete(MeetingTodoOwnerOrmModel).where(MeetingTodoOwnerOrmModel.todo_id.in_(todos)),
            delete(MeetingTodoOrmModel).where(MeetingTodoOrmModel.meeting_id == meeting_id),
            delete(MeetingDecisionOrmModel).where(MeetingDecisionOrmModel.meeting_id == meeting_id),
            delete(MeetingCardMentionOrmModel).where(MeetingCardMentionOrmModel.card_id.in_(cards)),
            delete(MeetingCardRevisionOrmModel).where(
                MeetingCardRevisionOrmModel.card_id.in_(cards)
            ),
            delete(MeetingFileOrmModel).where(MeetingFileOrmModel.meeting_id == meeting_id),
            delete(MeetingCardOrmModel).where(MeetingCardOrmModel.meeting_id == meeting_id),
            delete(MeetingEventOrmModel).where(MeetingEventOrmModel.meeting_id == meeting_id),
            delete(MeetingNotificationOrmModel).where(
                MeetingNotificationOrmModel.meeting_id == meeting_id
            ),
            delete(MeetingAttendeeOrmModel).where(MeetingAttendeeOrmModel.meeting_id == meeting_id),
            delete(MeetingTagOrmModel).where(MeetingTagOrmModel.meeting_id == meeting_id),
        ):
            await self._db.execute(statement)
        await self._db.execute(delete(MeetingOrmModel).where(MeetingOrmModel.id == meeting_id))

    async def anonymise_contact_copies(self, contact_id: int, at: datetime) -> None:
        await self._db.execute(
            update(MeetingAttendeeOrmModel)
            .where(MeetingAttendeeOrmModel.contact_id == contact_id)
            .values(name="", email=None, anonymised_at=at)
        )
        await self._db.execute(
            update(MeetingTodoOwnerOrmModel)
            .where(MeetingTodoOwnerOrmModel.contact_id == contact_id)
            .values(name="")
        )

    async def get_contact_usage(self, contact_ids: list[int]) -> list[ContactMeetingUsageRow]:
        if not contact_ids:
            return []
        ids = set(contact_ids)
        columns = (
            MeetingOrmModel.id,
            MeetingOrmModel.meeting_number,
            MeetingOrmModel.name,
            MeetingOrmModel.starts_at,
        )
        attending = await self._db.execute(
            select(MeetingAttendeeOrmModel.contact_id, *columns)
            .join(MeetingOrmModel, MeetingAttendeeOrmModel.meeting_id == MeetingOrmModel.id)
            .where(MeetingAttendeeOrmModel.contact_id.in_(ids), MeetingOrmModel.deleted.is_(False))
        )
        owning = await self._db.execute(
            select(MeetingTodoOwnerOrmModel.contact_id, *columns)
            .join(MeetingTodoOrmModel, MeetingTodoOwnerOrmModel.todo_id == MeetingTodoOrmModel.id)
            .join(MeetingOrmModel, MeetingTodoOrmModel.meeting_id == MeetingOrmModel.id)
            .where(MeetingTodoOwnerOrmModel.contact_id.in_(ids), MeetingOrmModel.deleted.is_(False))
        )
        seen: dict[tuple[int, int], tuple[datetime, ContactMeetingUsageRow]] = {}
        for contact_id, meeting_id, number, name, starts_at in [*attending.all(), *owning.all()]:
            if contact_id is None:
                continue
            row = ContactMeetingUsageRow(
                contact_id=contact_id, meeting_id=meeting_id, meeting_number=number, name=name
            )
            seen[(contact_id, meeting_id)] = (utc_aware(starts_at), row)
        ordered = sorted(seen.values(), key=lambda entry: entry[0], reverse=True)
        return [row for _, row in ordered]
