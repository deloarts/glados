"""
Concrete implementation of IMeetingSnapshotRepository using SQLAlchemy. A
snapshot's contents are JSON in the shapes written here; the contacts it
keeps copies of are listed in their own table, so anonymising a contact
finds its snapshots without reading every one.
"""

from datetime import date
from datetime import datetime
from datetime import time
from typing import Any

from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.workspace.adapters.outbound.persistence.models.meeting_snapshot_model import (
    MeetingSnapshotContactOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_snapshot_model import (
    MeetingSnapshotOrmModel,
)
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotAttendee
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotCard
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotDecision
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotFacts
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotFile
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotTodo
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotTodoOwner
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── To JSON ───────────────────────────────────────────────────────────


def _at(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _day(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _facts_json(facts: SnapshotFacts) -> dict[str, Any]:
    return {
        "meeting_number": facts.meeting_number,
        "name": facts.name,
        "starts_at": _at(facts.starts_at),
        "ends_at": _at(facts.ends_at),
        "location": facts.location,
        "next_meeting_date": _day(facts.next_meeting_date),
        "next_meeting_time": (
            facts.next_meeting_time.isoformat() if facts.next_meeting_time is not None else None
        ),
        "next_meeting_location": facts.next_meeting_location,
        "owner_kind": facts.owner_kind.value,
        "owner_id": facts.owner_id,
        "owner_number": facts.owner_number,
    }


def _todo_json(todo: SnapshotTodo) -> dict[str, Any]:
    return {
        "id": todo.id,
        "card_id": todo.card_id,
        "position": todo.position,
        "title": todo.title,
        "note": todo.note,
        "due_date": _day(todo.due_date),
        "done_at": _at(todo.done_at),
        "owners": [
            {"user_id": o.user_id, "contact_id": o.contact_id, "name": o.name} for o in todo.owners
        ],
    }


def _card_json(card: SnapshotCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "position": card.position,
        "scope": card.scope,
        "scope_icon": card.scope_icon.value if card.scope_icon is not None else None,
        "body": card.body,
        "internal": card.internal,
        "edit_version": card.edit_version,
        "created": _at(card.created),
        "creator_id": card.creator_id,
        "changed": _at(card.changed),
        "changed_by_id": card.changed_by_id,
        "decisions": [
            {
                "id": d.id,
                "card_id": d.card_id,
                "position": d.position,
                "text": d.text,
                "created": _at(d.created),
                "creator_id": d.creator_id,
            }
            for d in card.decisions
        ],
        "todos": [_todo_json(t) for t in card.todos],
    }


def _attendee_json(attendee: SnapshotAttendee) -> dict[str, Any]:
    return {
        "id": attendee.id,
        "kind": attendee.kind.value,
        "status": attendee.status.value,
        "position": attendee.position,
        "user_id": attendee.user_id,
        "contact_id": attendee.contact_id,
        "name": attendee.name,
        "email": attendee.email,
        "anonymised": attendee.anonymised,
    }


def _file_json(file: SnapshotFile) -> dict[str, Any]:
    return {
        "id": file.id,
        "file_name": file.file_name,
        "size_bytes": file.size_bytes,
        "category": file.category.value,
    }


# ── From JSON ─────────────────────────────────────────────────────────


def _parse_at(value: Any) -> datetime | None:
    return utc_aware(datetime.fromisoformat(value)) if value else None


def _parse_day(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def _required_at(value: Any) -> datetime:
    parsed = _parse_at(value)
    assert parsed is not None  # written for every snapshot
    return parsed


def _facts(data: dict[str, Any]) -> SnapshotFacts:
    return SnapshotFacts(
        meeting_number=data["meeting_number"],
        name=data["name"],
        starts_at=_required_at(data["starts_at"]),
        ends_at=_required_at(data["ends_at"]),
        location=data["location"],
        next_meeting_date=_parse_day(data["next_meeting_date"]),
        next_meeting_time=(
            time.fromisoformat(data["next_meeting_time"]) if data["next_meeting_time"] else None
        ),
        next_meeting_location=data["next_meeting_location"],
        owner_kind=MeetingOwnerKind(data["owner_kind"]),
        owner_id=data["owner_id"],
        owner_number=data["owner_number"],
    )


def _todo(data: dict[str, Any]) -> SnapshotTodo:
    return SnapshotTodo(
        id=data["id"],
        card_id=data["card_id"],
        position=data["position"],
        title=data["title"],
        note=data["note"],
        due_date=_parse_day(data["due_date"]),
        done_at=_parse_at(data["done_at"]),
        owners=[
            SnapshotTodoOwner(user_id=o["user_id"], contact_id=o["contact_id"], name=o["name"])
            for o in data["owners"]
        ],
    )


def _card(data: dict[str, Any]) -> SnapshotCard:
    return SnapshotCard(
        id=data["id"],
        position=data["position"],
        scope=data["scope"],
        scope_icon=MeetingScopeIcon(data["scope_icon"]) if data["scope_icon"] else None,
        body=data["body"],
        internal=data["internal"],
        edit_version=data["edit_version"],
        created=_required_at(data["created"]),
        creator_id=data["creator_id"],
        changed=_parse_at(data["changed"]),
        changed_by_id=data["changed_by_id"],
        decisions=[
            SnapshotDecision(
                id=d["id"],
                card_id=d["card_id"],
                position=d["position"],
                text=d["text"],
                created=_required_at(d["created"]),
                creator_id=d["creator_id"],
            )
            for d in data["decisions"]
        ],
        todos=[_todo(t) for t in data["todos"]],
    )


def _attendee(data: dict[str, Any]) -> SnapshotAttendee:
    return SnapshotAttendee(
        id=data["id"],
        kind=MeetingAttendeeKind(data["kind"]),
        status=MeetingAttendanceStatus(data["status"]),
        position=data["position"],
        user_id=data["user_id"],
        contact_id=data["contact_id"],
        name=data["name"],
        email=data["email"],
        anonymised=bool(data["anonymised"]),
    )


def _file(data: dict[str, Any]) -> SnapshotFile:
    return SnapshotFile(
        id=data["id"],
        file_name=data["file_name"],
        size_bytes=data["size_bytes"],
        category=MeetingFileCategory(data["category"]),
    )


def _to_entity(orm: MeetingSnapshotOrmModel) -> MeetingSnapshot:
    created = utc_aware(orm.created)
    assert created is not None  # non-null column
    return MeetingSnapshot(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        journal_entry_id=orm.journal_entry_id,
        kind=MeetingDistributionKind(orm.kind),
        created=created,
        actor_id=orm.actor_id,
        issue_number=orm.issue_number,
        issue_draft=orm.issue_draft,
        language=orm.language,
        options={str(k): bool(v) for k, v in (orm.options or {}).items()},
        byte_size=orm.byte_size,
        sha256=orm.sha256,
        facts=_facts(orm.meeting),
        cards=[_card(c) for c in orm.cards],
        attendees=[_attendee(a) for a in orm.attendees],
        files=[_file(f) for f in orm.files],
        attachments=[_file(f) for f in orm.attachments],
        recipients=list(orm.recipients),
        cc=list(orm.cc),
        subject=orm.subject,
    )


def _copies(snapshot: MeetingSnapshot) -> dict[str, Any]:
    """The columns that keep copies of names and addresses."""
    return {
        "cards": [_card_json(c) for c in snapshot.cards],
        "attendees": [_attendee_json(a) for a in snapshot.attendees],
        "recipients": list(snapshot.recipients),
        "cc": list(snapshot.cc),
    }


class SqlAlchemyMeetingSnapshotRepository:
    """Implements IMeetingSnapshotRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, snapshot: MeetingSnapshot) -> MeetingSnapshot:
        orm = MeetingSnapshotOrmModel(
            meeting_id=snapshot.meeting_id,
            journal_entry_id=snapshot.journal_entry_id,
            kind=snapshot.kind.value,
            created=snapshot.created,
            actor_id=snapshot.actor_id,
            issue_number=snapshot.issue_number,
            issue_draft=snapshot.issue_draft,
            language=snapshot.language,
            options=dict(snapshot.options),
            byte_size=snapshot.byte_size,
            sha256=snapshot.sha256,
            meeting=_facts_json(snapshot.facts),
            files=[_file_json(f) for f in snapshot.files],
            attachments=[_file_json(f) for f in snapshot.attachments],
            subject=snapshot.subject,
            **_copies(snapshot),
        )
        self._db.add(orm)
        await self._db.flush()
        for contact_id in sorted(snapshot.contact_ids()):
            self._db.add(MeetingSnapshotContactOrmModel(snapshot_id=orm.id, contact_id=contact_id))
        await self._db.flush()
        return _to_entity(orm)

    async def get_by_id(self, id: int) -> MeetingSnapshot | None:
        orm = await self._db.get(MeetingSnapshotOrmModel, id)
        return _to_entity(orm) if orm is not None else None

    async def get_by_meeting(self, meeting_id: int) -> list[MeetingSnapshot]:
        rows = await self._db.scalars(
            select(MeetingSnapshotOrmModel)
            .where(MeetingSnapshotOrmModel.meeting_id == meeting_id)
            .order_by(desc(MeetingSnapshotOrmModel.created), desc(MeetingSnapshotOrmModel.id))
        )
        return [_to_entity(row) for row in rows]

    async def last_sent(self, meeting_id: int) -> MeetingSnapshot | None:
        orm = await self._db.scalar(
            select(MeetingSnapshotOrmModel)
            .where(
                MeetingSnapshotOrmModel.meeting_id == meeting_id,
                MeetingSnapshotOrmModel.kind == MeetingDistributionKind.SENT.value,
            )
            .order_by(desc(MeetingSnapshotOrmModel.created), desc(MeetingSnapshotOrmModel.id))
            .limit(1)
        )
        return _to_entity(orm) if orm is not None else None

    async def get_with_contact(self, contact_id: int) -> list[MeetingSnapshot]:
        ids = select(MeetingSnapshotContactOrmModel.snapshot_id).where(
            MeetingSnapshotContactOrmModel.contact_id == contact_id
        )
        rows = await self._db.scalars(
            select(MeetingSnapshotOrmModel)
            .where(MeetingSnapshotOrmModel.id.in_(ids))
            .order_by(MeetingSnapshotOrmModel.id)
        )
        return [_to_entity(row) for row in rows]

    async def save_copies(self, snapshot: MeetingSnapshot) -> None:
        orm = await self._db.get(MeetingSnapshotOrmModel, snapshot.id)
        if orm is None:
            return
        for key, value in _copies(snapshot).items():
            setattr(orm, key, value)
        await self._db.flush()
