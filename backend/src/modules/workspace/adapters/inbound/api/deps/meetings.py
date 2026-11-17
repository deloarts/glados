"""Use case factories: meetings, their cards, decisions, todos, files,
scopes, tags, the distribution of their notes and the drafts of notes AI
agents prepare. Every meeting use case takes the same bundle of ports,
built once per request."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_contact_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IContactQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.misc import get_custom_mail
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.application.services.custom_mail import CustomMail
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.bindings import get_meeting_notes_journal
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_contact_link_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_card_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_file_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_meeting_notes_draft_repo,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_meeting_notification_queue,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_snapshot_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.adapters.outbound.live.meeting_presence import RedisMeetingPresence
from src.modules.workspace.application.use_cases.meeting import cards
from src.modules.workspace.application.use_cases.meeting import distribution
from src.modules.workspace.application.use_cases.meeting import files
from src.modules.workspace.application.use_cases.meeting import meetings
from src.modules.workspace.application.use_cases.meeting import notes_drafts
from src.modules.workspace.application.use_cases.meeting import scopes
from src.modules.workspace.application.use_cases.meeting import tags
from src.modules.workspace.application.use_cases.meeting import todos
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import IMeetingNotesJournal
from src.modules.workspace.ports.outbound.meeting_presence_port import IMeetingPresence
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_notes_draft_repository import (
    IMeetingNotesDraftRepository,
)
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


def get_meeting_ports(
    meeting_repo: IMeetingRepository = Depends(get_meeting_repo),
    card_repo: IMeetingCardRepository = Depends(get_meeting_card_repo),
    file_repo: IMeetingFileRepository = Depends(get_meeting_file_repo),
    queue: IMeetingNotificationQueue = Depends(get_meeting_notification_queue),
    project_repo: IProjectRepository = Depends(get_project_repo),
    product_repo: IProductRepository = Depends(get_product_repo),
    contact_queries: IContactQueries = Depends(get_contact_repo),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    snapshot_repo: IMeetingSnapshotRepository = Depends(get_meeting_snapshot_repo),
    journal: IMeetingNotesJournal = Depends(get_meeting_notes_journal),
) -> MeetingPorts:
    return MeetingPorts(
        meetings=meeting_repo,
        cards=card_repo,
        files=file_repo,
        queue=queue,
        projects=project_repo,
        products=product_repo,
        contacts=contact_queries,
        settings=settings_repo,
        storage=storage,
        uow=uow,
        snapshots=snapshot_repo,
        journal=journal,
    )


def get_meeting_presence() -> IMeetingPresence:
    return RedisMeetingPresence()


# ── Meetings ──────────────────────────────────────────────────────────


def get_list_meetings_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.ListMeetings:
    return meetings.ListMeetings(ports)


def get_meeting_use_case(ports: MeetingPorts = Depends(get_meeting_ports)) -> meetings.GetMeeting:
    return meetings.GetMeeting(ports)


def get_create_meeting_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.CreateMeeting:
    return meetings.CreateMeeting(ports)


def get_update_meeting_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.UpdateMeeting:
    return meetings.UpdateMeeting(ports)


def get_delete_meeting_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.DeleteMeeting:
    return meetings.DeleteMeeting(ports)


def get_mark_meeting_invalid_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.MarkMeetingInvalid:
    return meetings.MarkMeetingInvalid(ports)


def get_restore_meeting_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.RestoreMeeting:
    return meetings.RestoreMeeting(ports)


def get_create_follow_up_meeting_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.CreateFollowUpMeeting:
    return meetings.CreateFollowUpMeeting(ports)


def get_meeting_open_points_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.GetMeetingOpenPoints:
    return meetings.GetMeetingOpenPoints(ports)


def get_meeting_history_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.GetMeetingHistory:
    return meetings.GetMeetingHistory(ports)


def get_anonymise_meeting_attendee_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> meetings.AnonymiseMeetingAttendee:
    return meetings.AnonymiseMeetingAttendee(ports)


# ── Cards ─────────────────────────────────────────────────────────────


def get_meeting_card_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.GetMeetingCard:
    return cards.GetMeetingCard(ports)


def get_create_meeting_card_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.CreateMeetingCard:
    return cards.CreateMeetingCard(ports)


def get_update_meeting_card_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.UpdateMeetingCard:
    return cards.UpdateMeetingCard(ports)


def get_delete_meeting_card_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.DeleteMeetingCard:
    return cards.DeleteMeetingCard(ports)


def get_reorder_meeting_cards_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.ReorderMeetingCards:
    return cards.ReorderMeetingCards(ports)


def get_meeting_card_revisions_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.GetMeetingCardRevisions:
    return cards.GetMeetingCardRevisions(ports)


def get_restore_meeting_card_revision_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> cards.RestoreMeetingCardRevision:
    return cards.RestoreMeetingCardRevision(ports)


def get_announce_meeting_card_presence_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
    presence: IMeetingPresence = Depends(get_meeting_presence),
) -> cards.AnnounceMeetingCardPresence:
    return cards.AnnounceMeetingCardPresence(ports, presence)


# ── Decisions and todos ───────────────────────────────────────────────


def get_create_meeting_decision_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.CreateMeetingDecision:
    return todos.CreateMeetingDecision(ports)


def get_update_meeting_decision_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.UpdateMeetingDecision:
    return todos.UpdateMeetingDecision(ports)


def get_delete_meeting_decision_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.DeleteMeetingDecision:
    return todos.DeleteMeetingDecision(ports)


def get_create_meeting_todo_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.CreateMeetingTodo:
    return todos.CreateMeetingTodo(ports)


def get_update_meeting_todo_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.UpdateMeetingTodo:
    return todos.UpdateMeetingTodo(ports)


def get_delete_meeting_todo_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.DeleteMeetingTodo:
    return todos.DeleteMeetingTodo(ports)


def get_set_meeting_todo_done_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> todos.SetMeetingTodoDone:
    return todos.SetMeetingTodoDone(ports)


# ── Files ─────────────────────────────────────────────────────────────


def get_meeting_files_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> files.GetMeetingFiles:
    return files.GetMeetingFiles(ports)


def get_upload_meeting_file_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> files.UploadMeetingFile:
    return files.UploadMeetingFile(ports)


def get_rename_meeting_file_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> files.RenameMeetingFile:
    return files.RenameMeetingFile(ports)


def get_delete_meeting_file_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> files.DeleteMeetingFile:
    return files.DeleteMeetingFile(ports)


def get_download_meeting_file_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> files.DownloadMeetingFile:
    return files.DownloadMeetingFile(ports)


# ── Scopes ────────────────────────────────────────────────────────────


def get_meeting_scope_suggestions_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> scopes.GetMeetingScopeSuggestions:
    return scopes.GetMeetingScopeSuggestions(ports)


def get_meeting_tag_suggestions_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> tags.GetMeetingTagSuggestions:
    return tags.GetMeetingTagSuggestions(ports)


def get_rename_meeting_scope_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> scopes.RenameMeetingScope:
    return scopes.RenameMeetingScope(ports)


# ── Distribution ──────────────────────────────────────────────────────


def get_meeting_recipients(
    ports: MeetingPorts = Depends(get_meeting_ports),
    link_repo: IContactLinkRepository = Depends(get_contact_link_repo),
    customer_repo: ICustomerQueries = Depends(get_customer_repo),
) -> distribution.MeetingRecipients:
    return distribution.MeetingRecipients(ports, link_repo, customer_repo)


def get_meeting_issue_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> distribution.GetMeetingIssue:
    return distribution.GetMeetingIssue(ports)


def get_download_meeting_notes_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> distribution.DownloadMeetingNotes:
    return distribution.DownloadMeetingNotes(ports)


def get_print_meeting_notes_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> distribution.PrintMeetingNotes:
    return distribution.PrintMeetingNotes(ports)


def get_send_meeting_notes_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
    mail: CustomMail = Depends(get_custom_mail),
    recipients: distribution.MeetingRecipients = Depends(get_meeting_recipients),
) -> distribution.SendMeetingNotes:
    return distribution.SendMeetingNotes(ports, mail, recipients)


def get_meeting_recipient_suggestions_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
    recipients: distribution.MeetingRecipients = Depends(get_meeting_recipients),
) -> distribution.GetMeetingRecipientSuggestions:
    return distribution.GetMeetingRecipientSuggestions(ports, recipients)


def get_meeting_distribution_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> distribution.GetMeetingDistribution:
    return distribution.GetMeetingDistribution(ports)


def get_meeting_snapshot_use_case(
    ports: MeetingPorts = Depends(get_meeting_ports),
) -> distribution.GetMeetingSnapshot:
    return distribution.GetMeetingSnapshot(ports)


# ── Drafts of meeting notes ───────────────────────────────────────────


def get_notes_draft_ports(
    ports: MeetingPorts = Depends(get_meeting_ports),
    draft_repo: IMeetingNotesDraftRepository = Depends(get_meeting_notes_draft_repo),
    link_repo: IContactLinkRepository = Depends(get_contact_link_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> notes_drafts.NotesDraftPorts:
    return notes_drafts.NotesDraftPorts(
        meeting=ports, drafts=draft_repo, links=link_repo, users=user_repo
    )


def get_create_meeting_notes_draft_use_case(
    ports: notes_drafts.NotesDraftPorts = Depends(get_notes_draft_ports),
) -> notes_drafts.CreateMeetingNotesDraft:
    return notes_drafts.CreateMeetingNotesDraft(ports)


def get_list_meeting_notes_drafts_use_case(
    ports: notes_drafts.NotesDraftPorts = Depends(get_notes_draft_ports),
) -> notes_drafts.ListMeetingNotesDrafts:
    return notes_drafts.ListMeetingNotesDrafts(ports)


def get_meeting_notes_draft_use_case(
    ports: notes_drafts.NotesDraftPorts = Depends(get_notes_draft_ports),
) -> notes_drafts.GetMeetingNotesDraft:
    return notes_drafts.GetMeetingNotesDraft(ports)


def get_apply_meeting_notes_draft_use_case(
    ports: notes_drafts.NotesDraftPorts = Depends(get_notes_draft_ports),
) -> notes_drafts.ApplyMeetingNotesDraft:
    return notes_drafts.ApplyMeetingNotesDraft(ports)


def get_discard_meeting_notes_draft_use_case(
    ports: notes_drafts.NotesDraftPorts = Depends(get_notes_draft_ports),
) -> notes_drafts.DiscardMeetingNotesDraft:
    return notes_drafts.DiscardMeetingNotesDraft(ports)
