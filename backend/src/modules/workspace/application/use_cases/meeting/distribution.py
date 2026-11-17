"""
The distribution of a meeting's notes: the browser builds the PDF, and
printing, downloading or sending it here journals it in the export journal
and keeps a snapshot of what it contained. Also the issue the next PDFs
carry, the meeting's distribution list, one snapshot, and the recipients a
send suggests.

Every request names the cards the PDF contains with the edit versions it
was built from and the issue it carries; a card changed, added or deleted
since, or an issue that moved, answers 409 so the browser builds the PDF
again. The server computes the checksum of the PDF itself. A send is
journaled only after the mail server accepted the mail, and it raises the
meeting's issue.

Reading and downloading need a signed-in user, printing print rights, and
sending write:meetings together with send:mail.
"""

import hashlib
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.platform.application.services.custom_mail import CustomMail
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.mail_recipients import split_mail_recipients
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    DownloadMeetingNotesCommand,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingDistributionEntryResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingIssueResult
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingNotesBuild
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingPrintResult
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingRecipientSourceResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    MeetingRecipientSuggestionResult,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingSnapshotResult
from src.modules.workspace.application.dto.meeting_distribution_dto import PrintMeetingNotesCommand
from src.modules.workspace.application.dto.meeting_distribution_dto import SendMeetingNotesCommand
from src.modules.workspace.application.mappers.meeting_distribution_mapper import (
    MeetingDistributionMapper,
)
from src.modules.workspace.application.mappers.meeting_distribution_mapper import snapshot_user_ids
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting._support import load_meeting
from src.modules.workspace.application.use_cases.meeting._support import record
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.errors import MeetingFileNotFoundError
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingSnapshotNotFoundError
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.services.meeting_issue import IssueLabel
from src.modules.workspace.domain.services.meeting_issue import assert_cards_current
from src.modules.workspace.domain.services.meeting_issue import assert_label
from src.modules.workspace.domain.services.meeting_issue import changes_since
from src.modules.workspace.domain.services.meeting_issue import print_label
from src.modules.workspace.domain.services.meeting_issue import send_label
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.services.meeting_snapshot_builder import build_snapshot
from src.modules.workspace.domain.services.meeting_snapshot_builder import snapshot_file
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import IMeetingNotesJournal
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import MeetingJournalEntry
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import MeetingNotesExport
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingSnapshotRepository,
)
from src.shared_kernel.domain.services.clock import now_utc

# A PDF of meeting notes with its pictures stays far below this; the limit
# only keeps an arbitrary upload out of the journal.
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_COPIES = 10

_EVENT_KINDS = {
    MeetingDistributionKind.PRINTED: MeetingEventKind.PRINTED,
    MeetingDistributionKind.DOWNLOADED: MeetingEventKind.DOWNLOADED,
    MeetingDistributionKind.SENT: MeetingEventKind.SENT,
}


def _snapshots(ports: MeetingPorts) -> IMeetingSnapshotRepository:
    assert ports.snapshots is not None  # bound for every distribution route
    return ports.snapshots


def _journal(ports: MeetingPorts) -> IMeetingNotesJournal:
    assert ports.journal is not None  # bound for every distribution route
    return ports.journal


def _options(build: MeetingNotesBuild) -> dict[str, bool]:
    return build.options.model_dump()


def _assert_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise MeetingInvalidInputError("The notes are not a PDF.")
    if len(data) > MAX_PDF_BYTES:
        raise MeetingInvalidInputError(
            f"The PDF of the notes is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB."
        )


@dataclass
class _Prepared:
    """A PDF checked against the notes as they are, with the snapshot of
    what it contains, not yet written."""

    meeting: Meeting
    label: IssueLabel
    snapshot: MeetingSnapshot
    export: MeetingNotesExport
    files: list[MeetingFile] = field(default_factory=list)


async def _prepare(
    ports: MeetingPorts,
    actor: User,
    meeting_id: int,
    build: MeetingNotesBuild,
    kind: MeetingDistributionKind,
) -> _Prepared:
    """Checks the PDF against the notes and builds its snapshot. Only reads,
    so the caller may end the transaction before a printer or a mail server
    answers."""
    meeting = await load_meeting(ports, meeting_id)
    _assert_pdf(build.data)
    options = _options(build)
    cards = await ports.cards.get_cards(meeting.id)
    included = assert_cards_current(cards, options, {c.id: c.edit_version for c in build.cards})
    decisions = await ports.cards.get_decisions(meeting.id)
    todos = await ports.cards.get_todos(meeting.id)
    files = await ports.files.get_by_item_id(meeting.id)
    if kind == MeetingDistributionKind.SENT:
        label = send_label(meeting.issue_number)
    else:
        last_sent = await _snapshots(ports).last_sent(meeting.id)
        label = print_label(meeting.issue_number, changes_since(last_sent, cards, decisions, todos))
    assert_label(label, build.issue_number, build.draft)
    sha256 = hashlib.sha256(build.data).hexdigest()
    snapshot = build_snapshot(
        meeting,
        kind=kind,
        actor_id=actor.id,
        at=now_utc(),
        cards=included,
        decisions=decisions,
        todos=todos,
        files=files,
        options=options,
        label=label,
        language=build.language,
        byte_size=len(build.data),
        sha256=sha256,
    )
    export = MeetingNotesExport(
        meeting_id=meeting.id,
        meeting_public_id=meeting.public_id,
        revision=label.revision,
        language=build.language,
        options=options,
        report_version=build.report_version,
        byte_size=len(build.data),
        sha256=sha256,
    )
    return _Prepared(meeting=meeting, label=label, snapshot=snapshot, export=export, files=files)


async def _finish(
    ports: MeetingPorts,
    actor: User,
    prepared: _Prepared,
    entry: MeetingJournalEntry,
) -> MeetingDistributionEntryResult:
    """Writes the snapshot of a journaled PDF, stamps the meeting, raises
    its issue for a send, adds the history event and commits."""
    snapshot = await _snapshots(ports).save(
        replace(prepared.snapshot, journal_entry_id=entry.id, created=entry.created)
    )
    await ports.meetings.lock_for_update(prepared.meeting.id)
    meeting = await load_meeting(ports, prepared.meeting.id)
    details: dict[str, object] = {
        "journal_entry_id": entry.id,
        "snapshot_id": snapshot.id,
        "revision": prepared.label.revision,
        "issue_number": prepared.label.issue_number,
        "draft": prepared.label.draft,
    }
    if snapshot.kind == MeetingDistributionKind.SENT:
        # A send that crossed another one keeps the issue both PDFs carried.
        meeting.issue_number = max(meeting.issue_number, prepared.label.issue_number)
        meeting.last_sent_at = entry.created
        details["recipients"] = list(snapshot.recipients)
        details["cc"] = list(snapshot.cc)
    else:
        meeting.last_printed_at = entry.created
    if entry.copies is not None:
        details["copies"] = entry.copies
    await ports.meetings.save(meeting)
    await record(
        ports,
        meeting.id,
        _EVENT_KINDS[snapshot.kind],
        actor,
        at=entry.created,
        summary=prepared.label.revision,
        details=details,
    )
    await ports.uow.commit()
    log.info(
        f"Meeting {meeting.meeting_number} notes {snapshot.kind.value} "
        f"(issue {prepared.label.revision}, journal entry #{entry.id})."
    )
    users = await ports.meetings.get_users({entry.actor_id})
    return MeetingDistributionMapper.entry(entry, snapshot, users)


class _DistributionUseCase:
    def __init__(self, ports: MeetingPorts) -> None:
        self._ports = ports


# ── Issue ─────────────────────────────────────────────────────────────


class GetMeetingIssue(_DistributionUseCase):
    """The issue the PDF of a send carries, and the one a print or download
    carries now, with the cards that changed since the last send."""

    async def execute(self, actor: User, meeting_id: int) -> MeetingIssueResult:
        ports = self._ports
        meeting = await load_meeting(ports, meeting_id)
        cards = await ports.cards.get_cards(meeting.id)
        decisions = await ports.cards.get_decisions(meeting.id)
        todos = await ports.cards.get_todos(meeting.id)
        last_sent = await _snapshots(ports).last_sent(meeting.id)
        changes = changes_since(last_sent, cards, decisions, todos)
        return MeetingIssueResult(
            issue_number=meeting.issue_number,
            last_sent_at=meeting.last_sent_at,
            send=MeetingDistributionMapper.label(send_label(meeting.issue_number)),
            print=MeetingDistributionMapper.label(print_label(meeting.issue_number, changes)),
            changed_card_ids=changes.changed_card_ids,
            added_card_ids=changes.added_card_ids,
            removed_card_ids=changes.removed_card_ids,
        )


# ── Download and print ────────────────────────────────────────────────


class DownloadMeetingNotes(_DistributionUseCase):
    """Journals a PDF the browser saves for the user; the browser saves it
    once this answered."""

    async def execute(
        self, actor: User, meeting_id: int, cmd: DownloadMeetingNotesCommand
    ) -> MeetingDistributionEntryResult:
        kind = MeetingDistributionKind.DOWNLOADED
        prepared = await _prepare(self._ports, actor, meeting_id, cmd, kind)
        entry = await _journal(self._ports).record(actor, kind, prepared.export)
        return await _finish(self._ports, actor, prepared, entry)


class PrintMeetingNotes(_DistributionUseCase):
    """Sends the PDF to a printer. A print that reached the printer is
    journaled with its snapshot; a printer that failed answers a failed job
    and journals nothing."""

    async def execute(
        self, actor: User, meeting_id: int, cmd: PrintMeetingNotesCommand
    ) -> MeetingPrintResult:
        kind = MeetingDistributionKind.PRINTED
        prepared = await _prepare(self._ports, actor, meeting_id, cmd, kind)
        outcome = await _journal(self._ports).print(
            actor,
            prepared.export,
            cmd.data,
            printer_id=cmd.printer_id,
            copies=max(1, min(cmd.copies, MAX_COPIES)),
            two_sided=cmd.two_sided,
        )
        entry_result: MeetingDistributionEntryResult | None = None
        if outcome.entry is not None:
            entry_result = await _finish(self._ports, actor, prepared, outcome.entry)
        else:
            await self._ports.uow.commit()
        return MeetingPrintResult(
            job_id=outcome.job_id,
            printer_id=outcome.printer_id,
            copies=outcome.copies,
            status=outcome.status,
            error_message=outcome.error_message,
            attributes_substituted=outcome.attributes_substituted,
            entry=entry_result,
        )


# ── Recipients ────────────────────────────────────────────────────────


@dataclass
class _Suggestion:
    email: str
    name: str | None
    preselected: bool
    sources: list[MeetingRecipientSourceResult]
    contact_ids: set[int] = field(default_factory=set)


class _Suggestions:
    """Collects addresses by their lower case form, keeping the first
    spelling and name and every source."""

    def __init__(self) -> None:
        self._by_email: dict[str, _Suggestion] = {}

    def add(
        self,
        email: str | None,
        name: str | None,
        preselected: bool,
        source: MeetingRecipientSourceResult,
    ) -> None:
        address = (email or "").strip()
        if not address:
            return
        key = address.casefold()
        found = self._by_email.get(key)
        if found is None:
            found = _Suggestion(email=address, name=name or None, preselected=False, sources=[])
            self._by_email[key] = found
        found.preselected = found.preselected or preselected
        found.name = found.name or name or None
        found.sources.append(source)
        if source.contact_id is not None:
            found.contact_ids.add(source.contact_id)

    def all(self) -> list[_Suggestion]:
        """Pre-selected first, each group in the order found."""
        found = list(self._by_email.values())
        return [s for s in found if s.preselected] + [s for s in found if not s.preselected]


class MeetingRecipients:
    """Where the addresses of a send come from: the attendees that are
    contacts or guests with an address, the contacts of the project, its
    product's included, or of the product that receive meeting notes, the
    customer's other contacts and the customer's own address."""

    def __init__(
        self,
        ports: MeetingPorts,
        links: IContactLinkRepository,
        customers: ICustomerQueries,
    ) -> None:
        self._ports = ports
        self._links = links
        self._customers = customers

    async def _owner_links(
        self, meeting: Meeting
    ) -> tuple[list[tuple[int, bool, str]], int | None]:
        """The linked contacts as (contact id, receives meeting notes,
        source kind), and the customer of the owner."""
        ports = self._ports
        if meeting.project_id is not None:
            project = await ports.projects.get_by_id(meeting.project_id)
            if project is None:
                return [], None
            product = (
                await ports.products.get_by_id(project.product_id)
                if project.product_id is not None
                else None
            )
            product_links = (
                await self._links.get_links(ContactLinkOwner.PRODUCT, project.product_id)
                if project.product_id is not None
                else []
            )
            project_links = await self._links.get_links(ContactLinkOwner.PROJECT, project.id)
            resolved = ContactLinkRules.resolve_project_contacts(product_links, project_links)
            customer_id = project.customer_id or (product.customer_id if product else None)
            return [
                (
                    entry.contact_id,
                    entry.receives_meeting_notes,
                    "product_contact" if entry.inherited else "project_contact",
                )
                for entry in resolved
            ], customer_id
        assert meeting.product_id is not None
        product = await ports.products.get_by_id(meeting.product_id)
        links = await self._links.get_links(ContactLinkOwner.PRODUCT, meeting.product_id)
        return [
            (link.contact_id, link.receives_meeting_notes, "product_contact") for link in links
        ], (product.customer_id if product else None)

    async def suggest(self, meeting: Meeting, *, with_contacts: bool) -> list[_Suggestion]:
        found = _Suggestions()
        for attendee in meeting.attendees:
            if attendee.kind == MeetingAttendeeKind.USER or attendee.anonymised_at is not None:
                continue
            found.add(
                attendee.email,
                attendee.name,
                True,
                MeetingRecipientSourceResult(
                    kind="attendee",
                    attendee_id=attendee.id,
                    attendee_status=attendee.status,
                    contact_id=attendee.contact_id,
                ),
            )
        if not with_contacts:
            return found.all()

        linked, customer_id = await self._owner_links(meeting)
        customer_contacts = (
            await self._ports.contacts.get_mail_contacts_of_customer(customer_id)
            if customer_id is not None
            else []
        )
        receiving = [(cid, kind) for cid, receives, kind in linked if receives]
        contacts = {
            c.id: c for c in await self._ports.contacts.get_by_ids([cid for cid, _ in receiving])
        }
        for contact_id, kind in receiving:
            contact = contacts.get(contact_id)
            if contact is None or contact.archived or contact.anonymised:
                continue
            found.add(
                contact.email,
                contact.name,
                True,
                MeetingRecipientSourceResult(kind=kind, contact_id=contact.id),
            )
        for contact in customer_contacts:
            found.add(
                contact.email,
                contact.name,
                False,
                MeetingRecipientSourceResult(
                    kind="customer_contact", contact_id=contact.id, customer_id=customer_id
                ),
            )
        if customer_id is not None:
            customer = await self._customers.get_by_id(customer_id)
            if customer is not None and not customer.archived:
                found.add(
                    customer.email,
                    customer.name,
                    False,
                    MeetingRecipientSourceResult(kind="customer", customer_id=customer.id),
                )
        return found.all()

    async def contact_ids_of(self, meeting: Meeting, addresses: list[str]) -> list[int]:
        """The contacts whose addresses are among the given ones."""
        wanted = {address.casefold() for address in addresses}
        ids: set[int] = set()
        for suggestion in await self.suggest(meeting, with_contacts=True):
            if suggestion.email.casefold() in wanted:
                ids |= suggestion.contact_ids
        return sorted(ids)


class GetMeetingRecipientSuggestions:
    """The addresses the send dialog offers. Contacts other than the
    attendees are personal data, so they need read:contacts; without it the
    attendees alone are offered."""

    def __init__(self, ports: MeetingPorts, recipients: MeetingRecipients) -> None:
        self._ports = ports
        self._recipients = recipients

    async def execute(self, actor: User, meeting_id: int) -> list[MeetingRecipientSuggestionResult]:
        meeting = await load_meeting(self._ports, meeting_id)
        with_contacts = actor.has_permission(Permission.READ_CONTACTS)
        return [
            MeetingRecipientSuggestionResult(
                email=s.email, name=s.name, preselected=s.preselected, sources=s.sources
            )
            for s in await self._recipients.suggest(meeting, with_contacts=with_contacts)
        ]


# ── Send ──────────────────────────────────────────────────────────────


def _pdf_name(meeting: Meeting, cmd: SendMeetingNotesCommand) -> str:
    name = (cmd.file_name or "").strip().replace("/", "_").replace("\\", "_")
    if not name:
        name = f"{meeting.meeting_number}.pdf"
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


class SendMeetingNotes:
    """Mails the PDF, and the documents asked for, to the recipients. Only
    once the mail server accepted the mail is the send journaled, its
    snapshot kept, the issue raised and the history written; a refusal
    answers its error and records nothing."""

    def __init__(
        self, ports: MeetingPorts, mail: CustomMail, recipients: MeetingRecipients
    ) -> None:
        self._ports = ports
        self._mail = mail
        self._recipients = recipients

    @staticmethod
    def _documents(files: list[MeetingFile], file_ids: list[int]) -> list[MeetingFile]:
        by_id = {f.id: f for f in files}
        chosen: list[MeetingFile] = []
        for file_id in dict.fromkeys(file_ids):
            file = by_id.get(file_id)
            if file is None:
                raise MeetingFileNotFoundError(f"File #{file_id} not found.")
            chosen.append(file)
        return chosen

    async def execute(
        self, actor: User, meeting_id: int, cmd: SendMeetingNotesCommand
    ) -> MeetingDistributionEntryResult:
        MeetingRules.assert_can_write(actor)
        self._mail.assert_can_send(actor)
        kind = MeetingDistributionKind.SENT
        prepared = await _prepare(self._ports, actor, meeting_id, cmd, kind)
        meeting = prepared.meeting
        MeetingRules.assert_editable(meeting)
        to = split_mail_recipients(cmd.to)
        cc = split_mail_recipients(cmd.cc) if cmd.cc else []
        if not to:
            raise MeetingInvalidInputError("At least one recipient is needed.")

        pdf = MailAttachment(_pdf_name(meeting, cmd), "application/pdf", cmd.data)
        documents = self._documents(prepared.files, cmd.attach_file_ids)
        # The sizes are known from the rows, so documents that do not fit
        # are refused before any of them is read.
        await self._mail.assert_attachments_fit(
            [(pdf.file_name, pdf.size)] + [(f.file_name, f.size_bytes) for f in documents]
        )
        attachments = [pdf]
        storage = self._ports.storage
        if documents and storage is None:
            raise MeetingInvalidInputError("File storage is off, so no document can be attached.")
        for file in documents:
            assert storage is not None
            data, _ = await storage.download(file.storage_path)
            attachments.append(MailAttachment(file.file_name, file.mime_type, data))

        recipient_contact_ids = await self._recipients.contact_ids_of(meeting, to + cc)
        await self._mail.send(
            actor,
            to=", ".join(to),
            subject=cmd.subject,
            html_body=cmd.html_body,
            cc=", ".join(cc) or None,
            attachments=attachments,
        )

        prepared.snapshot = replace(
            prepared.snapshot,
            recipients=to,
            cc=cc,
            subject=cmd.subject,
            attachments=[snapshot_file(f) for f in documents],
            recipient_contact_ids=recipient_contact_ids,
        )
        entry = await _journal(self._ports).record(actor, kind, prepared.export, recipients=to + cc)
        return await _finish(self._ports, actor, prepared, entry)


# ── Distribution list and snapshots ───────────────────────────────────


class GetMeetingDistribution(_DistributionUseCase):
    """Every print, download and send of the notes, newest first, each with
    its snapshot."""

    async def execute(self, actor: User, meeting_id: int) -> list[MeetingDistributionEntryResult]:
        meeting = await load_meeting(self._ports, meeting_id)
        entries = await _journal(self._ports).entries(meeting.public_id)
        snapshots = {
            s.journal_entry_id: s for s in await _snapshots(self._ports).get_by_meeting(meeting.id)
        }
        users = await self._ports.meetings.get_users({e.actor_id for e in entries})
        return [
            MeetingDistributionMapper.entry(entry, snapshots.get(entry.id), users)
            for entry in entries
        ]


class GetMeetingSnapshot(_DistributionUseCase):
    async def execute(
        self, actor: User, meeting_id: int, snapshot_id: int
    ) -> MeetingSnapshotResult:
        meeting = await load_meeting(self._ports, meeting_id)
        snapshot = await _snapshots(self._ports).get_by_id(snapshot_id)
        if snapshot is None or snapshot.meeting_id != meeting.id:
            raise MeetingSnapshotNotFoundError(f"Snapshot #{snapshot_id} not found.")
        users = await self._ports.meetings.get_users(snapshot_user_ids(snapshot))
        return MeetingDistributionMapper.snapshot(snapshot, users)
