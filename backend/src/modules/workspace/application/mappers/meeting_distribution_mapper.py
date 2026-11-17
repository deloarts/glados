"""
Converts the journal entries and snapshots of meeting notes into their
result DTOs. The users they name are resolved once per request and handed
in as a map.
"""

from collections.abc import Mapping

from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingDistributionEntryResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingIssueLabelResult
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingSnapshotAttendeeResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingSnapshotCardResult
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingSnapshotDecisionResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingSnapshotFactsResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingSnapshotFileResult
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingSnapshotResult
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingSnapshotTodoResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoOwnerResult
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotAttendee
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotCard
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotFile
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotTodo
from src.modules.workspace.domain.services.meeting_issue import IssueLabel
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import MeetingJournalEntry

Users = Mapping[int, User]


def _user(users: Users, user_id: int | None) -> PublicUserResult | None:
    if user_id is None:
        return None
    user = users.get(user_id)
    return UserMapper.to_public_result(user) if user is not None else None


def _name(users: Users, user_id: int | None, copy: str | None) -> str:
    if user_id is not None and user_id in users:
        return users[user_id].full_name
    return copy or ""


def snapshot_user_ids(snapshot: MeetingSnapshot) -> set[int]:
    ids = {snapshot.actor_id}
    for card in snapshot.cards:
        ids.add(card.creator_id)
        if card.changed_by_id is not None:
            ids.add(card.changed_by_id)
        ids.update(d.creator_id for d in card.decisions)
        for todo in card.todos:
            ids.update(o.user_id for o in todo.owners if o.user_id is not None)
    ids.update(a.user_id for a in snapshot.attendees if a.user_id is not None)
    return ids


class MeetingDistributionMapper:
    @staticmethod
    def label(label: IssueLabel) -> MeetingIssueLabelResult:
        return MeetingIssueLabelResult(
            issue_number=label.issue_number, draft=label.draft, revision=label.revision
        )

    @staticmethod
    def entry(
        entry: MeetingJournalEntry, snapshot: MeetingSnapshot | None, users: Users
    ) -> MeetingDistributionEntryResult:
        if snapshot is not None:
            label = IssueLabel(snapshot.issue_number, snapshot.issue_draft)
            recipients, cc, subject = snapshot.recipients, snapshot.cc, snapshot.subject
        else:
            label = IssueLabel(0, draft=True)
            recipients, cc, subject = entry.recipients, [], None
        return MeetingDistributionEntryResult(
            journal_entry_id=entry.id,
            journal_entry_public_id=entry.public_id,
            kind=entry.kind,
            at=entry.created,
            actor=_user(users, entry.actor_id),
            actor_full_name=entry.actor_full_name,
            issue=MeetingDistributionMapper.label(label),
            language=entry.language,
            options=entry.options,
            report_version=entry.report_version,
            byte_size=entry.byte_size,
            sha256=entry.sha256,
            recipients=list(recipients),
            cc=list(cc),
            subject=subject,
            copies=entry.copies,
            print_job_id=entry.print_job_id,
            snapshot_id=snapshot.id if snapshot is not None else None,
        )

    @staticmethod
    def _todo(todo: SnapshotTodo, users: Users) -> MeetingSnapshotTodoResult:
        return MeetingSnapshotTodoResult(
            id=todo.id,
            card_id=todo.card_id,
            position=todo.position,
            title=todo.title,
            note=todo.note,
            due_date=todo.due_date,
            done=todo.done_at is not None,
            done_at=todo.done_at,
            owners=[
                MeetingTodoOwnerResult(
                    user=_user(users, o.user_id),
                    contact_id=o.contact_id,
                    name=_name(users, o.user_id, o.name),
                )
                for o in todo.owners
            ],
        )

    @staticmethod
    def _card(card: SnapshotCard, users: Users) -> MeetingSnapshotCardResult:
        return MeetingSnapshotCardResult(
            id=card.id,
            position=card.position,
            scope=card.scope,
            scope_icon=card.scope_icon,
            body=card.body,
            internal=card.internal,
            edit_version=card.edit_version,
            created=card.created,
            creator=_user(users, card.creator_id),
            changed=card.changed,
            changed_by=_user(users, card.changed_by_id),
            decisions=[
                MeetingSnapshotDecisionResult(
                    id=d.id,
                    card_id=d.card_id,
                    position=d.position,
                    text=d.text,
                    created=d.created,
                    creator=_user(users, d.creator_id),
                )
                for d in card.decisions
            ],
            todos=[MeetingDistributionMapper._todo(t, users) for t in card.todos],
        )

    @staticmethod
    def _attendee(attendee: SnapshotAttendee, users: Users) -> MeetingSnapshotAttendeeResult:
        return MeetingSnapshotAttendeeResult(
            id=attendee.id,
            kind=attendee.kind,
            status=attendee.status,
            position=attendee.position,
            user=_user(users, attendee.user_id),
            contact_id=attendee.contact_id,
            name=_name(users, attendee.user_id, attendee.name),
            email=attendee.email,
            anonymised=attendee.anonymised,
        )

    @staticmethod
    def _file(file: SnapshotFile) -> MeetingSnapshotFileResult:
        return MeetingSnapshotFileResult(
            id=file.id, file_name=file.file_name, size_bytes=file.size_bytes, category=file.category
        )

    @staticmethod
    def snapshot(snapshot: MeetingSnapshot, users: Users) -> MeetingSnapshotResult:
        facts = snapshot.facts
        return MeetingSnapshotResult(
            id=snapshot.id,
            public_id=snapshot.public_id,
            meeting_id=snapshot.meeting_id,
            journal_entry_id=snapshot.journal_entry_id,
            kind=snapshot.kind,
            created=snapshot.created,
            actor=_user(users, snapshot.actor_id),
            issue=MeetingDistributionMapper.label(
                IssueLabel(snapshot.issue_number, snapshot.issue_draft)
            ),
            language=snapshot.language,
            options=snapshot.options,
            byte_size=snapshot.byte_size,
            sha256=snapshot.sha256,
            meeting=MeetingSnapshotFactsResult(
                meeting_number=facts.meeting_number,
                name=facts.name,
                starts_at=facts.starts_at,
                ends_at=facts.ends_at,
                location=facts.location,
                next_meeting_date=facts.next_meeting_date,
                next_meeting_time=facts.next_meeting_time,
                next_meeting_location=facts.next_meeting_location,
                owner_kind=facts.owner_kind,
                owner_id=facts.owner_id,
                owner_number=facts.owner_number,
            ),
            cards=[MeetingDistributionMapper._card(c, users) for c in snapshot.cards],
            attendees=[MeetingDistributionMapper._attendee(a, users) for a in snapshot.attendees],
            files=[MeetingDistributionMapper._file(f) for f in snapshot.files],
            attachments=[MeetingDistributionMapper._file(f) for f in snapshot.attachments],
            recipients=list(snapshot.recipients),
            cc=list(snapshot.cc),
            subject=snapshot.subject,
        )
