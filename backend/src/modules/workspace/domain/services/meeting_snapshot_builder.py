"""
Builds the snapshot of a PDF of meeting notes from the meeting as it is:
its facts, the cards the PDF contains with their decisions and, when the
PDF lists them, their todos, the attendees and the documents. No I/O.
"""

from collections.abc import Mapping
from datetime import datetime

from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotAttendee
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotCard
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotDecision
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotFacts
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotFile
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotTodo
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotTodoOwner
from src.modules.workspace.domain.services.meeting_issue import OPTION_INCLUDE_TODOS
from src.modules.workspace.domain.services.meeting_issue import OPTION_LIST_DOCUMENTS
from src.modules.workspace.domain.services.meeting_issue import IssueLabel
from src.modules.workspace.domain.services.meeting_issue import option
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind


def snapshot_file(file: MeetingFile) -> SnapshotFile:
    return SnapshotFile(
        id=file.id, file_name=file.file_name, size_bytes=file.size_bytes, category=file.category
    )


def _todo(todo: MeetingTodo) -> SnapshotTodo:
    return SnapshotTodo(
        id=todo.id,
        card_id=todo.card_id,
        position=todo.position,
        title=todo.title,
        note=todo.note,
        due_date=todo.due_date,
        done_at=todo.done_at,
        owners=[
            SnapshotTodoOwner(user_id=o.user_id, contact_id=o.contact_id, name=o.name)
            for o in todo.owners
        ],
    )


def _card(
    card: MeetingCard,
    decisions: list[MeetingDecision],
    todos: list[MeetingTodo],
    *,
    with_todos: bool,
) -> SnapshotCard:
    return SnapshotCard(
        id=card.id,
        position=card.position,
        scope=card.scope,
        scope_icon=card.scope_icon,
        body=card.body,
        internal=card.internal,
        edit_version=card.edit_version,
        created=card.created,
        creator_id=card.creator_id,
        changed=card.changed,
        changed_by_id=card.changed_by_id,
        decisions=[
            SnapshotDecision(
                id=d.id,
                card_id=d.card_id,
                position=d.position,
                text=d.text,
                created=d.created,
                creator_id=d.creator_id,
            )
            for d in sorted(decisions, key=lambda d: (d.position, d.id))
            if d.card_id == card.id
        ],
        todos=(
            [
                _todo(t)
                for t in sorted(todos, key=lambda t: (t.position, t.id))
                if t.card_id == card.id
            ]
            if with_todos
            else []
        ),
    )


def build_snapshot(
    meeting: Meeting,
    *,
    kind: MeetingDistributionKind,
    actor_id: int,
    at: datetime,
    cards: list[MeetingCard],
    decisions: list[MeetingDecision],
    todos: list[MeetingTodo],
    files: list[MeetingFile],
    options: Mapping[str, bool],
    label: IssueLabel,
    language: str,
    byte_size: int,
    sha256: str,
) -> MeetingSnapshot:
    """The snapshot of a PDF containing `cards`, the cards the options
    include in their order. Its journal entry is named once written."""
    with_todos = option(options, OPTION_INCLUDE_TODOS)
    return MeetingSnapshot(
        id=0,
        meeting_id=meeting.id,
        journal_entry_id=0,
        kind=kind,
        created=at,
        actor_id=actor_id,
        issue_number=label.issue_number,
        issue_draft=label.draft,
        language=language,
        options=dict(options),
        byte_size=byte_size,
        sha256=sha256,
        facts=SnapshotFacts(
            meeting_number=meeting.meeting_number,
            name=meeting.name,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            location=meeting.location,
            next_meeting_date=meeting.next_meeting_date,
            next_meeting_time=meeting.next_meeting_time,
            next_meeting_location=meeting.next_meeting_location,
            owner_kind=meeting.owner_kind,
            owner_id=meeting.owner_id,
            owner_number=meeting.owner_number,
        ),
        cards=[_card(c, decisions, todos, with_todos=with_todos) for c in cards],
        attendees=[
            SnapshotAttendee(
                id=a.id,
                kind=a.kind,
                status=a.status,
                position=a.position,
                user_id=a.user_id,
                contact_id=a.contact_id,
                name=a.name,
                email=a.email,
                anonymised=a.anonymised_at is not None,
            )
            for a in meeting.attendees
        ],
        files=(
            [snapshot_file(f) for f in sorted(files, key=lambda f: (f.created, f.id))]
            if option(options, OPTION_LIST_DOCUMENTS)
            else []
        ),
    )
