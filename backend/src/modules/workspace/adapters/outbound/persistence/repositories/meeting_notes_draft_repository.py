"""
Concrete implementation of IMeetingNotesDraftRepository using SQLAlchemy. A
draft's contents are JSON in the shapes written here. The number and name
of the meeting it adds to, or the number of the project or product it
proposes a meeting of, are read along for the lists that show it.
"""

from datetime import date
from datetime import datetime
from datetime import time
from typing import Any

from sqlalchemy import delete
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import MeetingOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.meeting_notes_draft_model import (
    MeetingNotesDraftOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftAttendee
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftCard
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNewMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftNextMeeting
from src.modules.workspace.domain.entities.meeting_notes_draft import DraftTodo
from src.modules.workspace.domain.entities.meeting_notes_draft import MeetingNotesDraft
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── To JSON ───────────────────────────────────────────────────────────


def _new_meeting_json(value: DraftNewMeeting | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "name": value.name,
        "starts_at": value.starts_at.isoformat(),
        "ends_at": value.ends_at.isoformat(),
        "location": value.location,
        "tags": list(value.tags),
    }


def _next_meeting_json(value: DraftNextMeeting | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "date": value.day.isoformat(),
        "time": value.start_time.isoformat() if value.start_time is not None else None,
        "location": value.location,
    }


def _attendee_json(value: DraftAttendee) -> dict[str, Any]:
    return {"name": value.name, "status": value.status.value, "email": value.email}


def _todo_json(value: DraftTodo) -> dict[str, Any]:
    return {
        "title": value.title,
        "note": value.note,
        "due_date": value.due_date.isoformat() if value.due_date is not None else None,
        "owners": list(value.owners),
    }


def _card_json(value: DraftCard) -> dict[str, Any]:
    return {
        "scope": value.scope,
        "scope_icon": value.scope_icon.value if value.scope_icon is not None else None,
        "body": value.body,
        "internal": value.internal,
        "decisions": list(value.decisions),
        "todos": [_todo_json(t) for t in value.todos],
        "review_note": value.review_note,
    }


# ── From JSON ─────────────────────────────────────────────────────────


def _required_at(value: Any) -> datetime:
    parsed = utc_aware(datetime.fromisoformat(value))
    assert parsed is not None
    return parsed


def _new_meeting(data: dict[str, Any] | None) -> DraftNewMeeting | None:
    if not data:
        return None
    return DraftNewMeeting(
        name=data["name"],
        starts_at=_required_at(data["starts_at"]),
        ends_at=_required_at(data["ends_at"]),
        location=data["location"],
        tags=list(data["tags"]),
    )


def _next_meeting(data: dict[str, Any] | None) -> DraftNextMeeting | None:
    if not data:
        return None
    return DraftNextMeeting(
        day=date.fromisoformat(data["date"]),
        start_time=time.fromisoformat(data["time"]) if data["time"] else None,
        location=data["location"],
    )


def _attendee(data: dict[str, Any]) -> DraftAttendee:
    return DraftAttendee(
        name=data["name"],
        status=MeetingAttendanceStatus(data["status"]),
        email=data["email"],
    )


def _todo(data: dict[str, Any]) -> DraftTodo:
    return DraftTodo(
        title=data["title"],
        note=data["note"],
        due_date=date.fromisoformat(data["due_date"]) if data["due_date"] else None,
        owners=list(data["owners"]),
    )


def _card(data: dict[str, Any]) -> DraftCard:
    return DraftCard(
        scope=data["scope"],
        scope_icon=MeetingScopeIcon(data["scope_icon"]) if data["scope_icon"] else None,
        body=data["body"],
        internal=bool(data["internal"]),
        decisions=list(data["decisions"]),
        todos=[_todo(t) for t in data["todos"]],
        review_note=data["review_note"],
    )


def _to_entity(orm: MeetingNotesDraftOrmModel) -> MeetingNotesDraft:
    created = utc_aware(orm.created)
    assert created is not None  # non-null column
    return MeetingNotesDraft(
        id=orm.id,
        public_id=orm.public_id,
        creator_id=orm.creator_id,
        created=created,
        meeting_id=orm.meeting_id,
        project_id=orm.project_id,
        product_id=orm.product_id,
        new_meeting=_new_meeting(orm.new_meeting),
        attendees=[_attendee(a) for a in orm.attendees],
        cards=[_card(c) for c in orm.cards],
        next_meeting=_next_meeting(orm.next_meeting),
        review_note=orm.review_note,
        token_name=orm.token_name,
    )


def _to_dict(draft: MeetingNotesDraft) -> dict[str, Any]:
    return {
        "creator_id": draft.creator_id,
        "created": draft.created,
        "meeting_id": draft.meeting_id,
        "project_id": draft.project_id,
        "product_id": draft.product_id,
        "token_name": draft.token_name,
        "new_meeting": _new_meeting_json(draft.new_meeting),
        "next_meeting": _next_meeting_json(draft.next_meeting),
        "attendees": [_attendee_json(a) for a in draft.attendees],
        "cards": [_card_json(c) for c in draft.cards],
        "review_note": draft.review_note,
    }


class SqlAlchemyMeetingNotesDraftRepository:
    """Implements IMeetingNotesDraftRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _with_labels(self, rows: list[MeetingNotesDraftOrmModel]) -> list[MeetingNotesDraft]:
        """The drafts with the numbers and names their lists show."""
        drafts = [_to_entity(r) for r in rows]
        meeting_ids = {d.meeting_id for d in drafts if d.meeting_id is not None}
        project_ids = {d.project_id for d in drafts if d.project_id is not None}
        product_ids = {d.product_id for d in drafts if d.product_id is not None}
        meetings: dict[int, tuple[str, str]] = {}
        if meeting_ids:
            result = await self._db.execute(
                select(
                    MeetingOrmModel.id, MeetingOrmModel.meeting_number, MeetingOrmModel.name
                ).where(MeetingOrmModel.id.in_(meeting_ids))
            )
            meetings = {row.id: (row.meeting_number, row.name) for row in result}
        projects: dict[int, str] = {}
        if project_ids:
            result = await self._db.execute(
                select(ProjectOrmModel.id, ProjectOrmModel.project_number).where(
                    ProjectOrmModel.id.in_(project_ids)
                )
            )
            projects = {row.id: row.project_number for row in result}
        products: dict[int, str] = {}
        if product_ids:
            result = await self._db.execute(
                select(ProductOrmModel.id, ProductOrmModel.product_number).where(
                    ProductOrmModel.id.in_(product_ids)
                )
            )
            products = {row.id: row.product_number for row in result}
        for draft in drafts:
            if draft.meeting_id is not None and draft.meeting_id in meetings:
                draft.meeting_number, draft.meeting_name = meetings[draft.meeting_id]
            elif draft.project_id is not None:
                draft.owner_number = projects.get(draft.project_id)
            elif draft.product_id is not None:
                draft.owner_number = products.get(draft.product_id)
        return drafts

    async def save(self, draft: MeetingNotesDraft) -> MeetingNotesDraft:
        values = _to_dict(draft)
        if draft.id == 0:
            orm = MeetingNotesDraftOrmModel(**values, public_id=draft.public_id)
            self._db.add(orm)
        else:
            found = await self._db.get(MeetingNotesDraftOrmModel, draft.id)
            assert found is not None
            orm = found
            for key, value in values.items():
                setattr(orm, key, value)
        await self._db.flush()
        return (await self._with_labels([orm]))[0]

    async def get_by_id(self, id: int) -> MeetingNotesDraft | None:
        orm = await self._db.get(MeetingNotesDraftOrmModel, id)
        return (await self._with_labels([orm]))[0] if orm is not None else None

    async def get_by_creator(
        self,
        creator_id: int,
        *,
        meeting_id: int | None = None,
        project_id: int | None = None,
        product_id: int | None = None,
    ) -> list[MeetingNotesDraft]:
        stmt = select(MeetingNotesDraftOrmModel).where(
            MeetingNotesDraftOrmModel.creator_id == creator_id
        )
        if meeting_id is not None:
            stmt = stmt.where(MeetingNotesDraftOrmModel.meeting_id == meeting_id)
        if project_id is not None:
            stmt = stmt.where(MeetingNotesDraftOrmModel.project_id == project_id)
        if product_id is not None:
            stmt = stmt.where(MeetingNotesDraftOrmModel.product_id == product_id)
        stmt = stmt.order_by(
            desc(MeetingNotesDraftOrmModel.created), desc(MeetingNotesDraftOrmModel.id)
        )
        rows = list((await self._db.scalars(stmt)).all())
        return await self._with_labels(rows)

    async def delete(self, draft: MeetingNotesDraft) -> None:
        await self._db.execute(
            delete(MeetingNotesDraftOrmModel).where(MeetingNotesDraftOrmModel.id == draft.id)
        )

    async def delete_created_before(self, before: datetime) -> int:
        ids = list(
            (
                await self._db.scalars(
                    select(MeetingNotesDraftOrmModel.id).where(
                        MeetingNotesDraftOrmModel.created < before
                    )
                )
            ).all()
        )
        if ids:
            await self._db.execute(
                delete(MeetingNotesDraftOrmModel).where(MeetingNotesDraftOrmModel.id.in_(ids))
            )
        return len(ids)
