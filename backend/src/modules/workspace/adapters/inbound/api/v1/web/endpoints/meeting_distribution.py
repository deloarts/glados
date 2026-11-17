"""
Web surface endpoints for the distribution of meeting notes. The browser
builds the PDF and posts it here as a multipart form with how it built it:
the `options` as a JSON object, the `cards` it contains with their edit
versions as a JSON array, and the issue it carries. A card changed, added or
deleted since, or an issue that moved, answers 409 with the code
MeetingNotesOutdatedError, and the browser builds the PDF again.

A download is journaled before the browser saves the file, a print once the
printer took it, and a send once the mail server accepted it. Every route
needs a signed-in user; printing checks print rights, sending write:meetings
and send:mail, and the recipient suggestions name contacts only with
read:contacts.
"""

from fastapi import Depends
from fastapi import Form
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.mail_schema import validated_recipients
from src.modules.platform.adapters.inbound.api.upload_limits import max_upload_size
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.language import Language
from src.modules.workspace.adapters.inbound.api.deps import meetings as deps
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    MeetingDistributionEntryResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    MeetingIssueResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    MeetingPrintResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    MeetingRecipientSuggestionResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    MeetingSnapshotResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    parse_cards,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    parse_options,
)
from src.modules.workspace.adapters.inbound.api.schemas.meeting_distribution_schema import (
    unprocessable,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import (
    DownloadMeetingNotesCommand,
)
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingCardVersion
from src.modules.workspace.application.dto.meeting_distribution_dto import MeetingNotesOptions
from src.modules.workspace.application.dto.meeting_distribution_dto import PrintMeetingNotesCommand
from src.modules.workspace.application.dto.meeting_distribution_dto import SendMeetingNotesCommand
from src.modules.workspace.application.use_cases.meeting import distribution
from src.modules.workspace.application.use_cases.meeting.distribution import MAX_COPIES
from src.modules.workspace.application.use_cases.meeting.distribution import MAX_PDF_BYTES

router = APIRouter()

_OPTIONS = Form(
    default=None,
    max_length=500,
    description=(
        'The switches as a JSON object, such as {"include_todos": true, '
        '"include_internal": false, "list_documents": true}.'
    ),
)
_CARDS = Form(
    ...,
    max_length=50_000,
    description='The cards of the PDF as a JSON array, such as [{"id": 3, "edit_version": 2}].',
)
_ISSUE = Form(..., ge=0, description="The issue printed on the PDF.")
_DRAFT = Form(
    default=False, description="Whether the PDF says it is a draft after the issue, or a draft."
)


def _as[T: BaseModel](model: type[T], result: BaseModel) -> T:
    return model.model_validate(result.model_dump())


def _build(
    file_data: bytes,
    file_name: str | None,
    language: Language,
    report_version: str,
    options: str | None,
    cards: str,
    issue_number: int,
    draft: bool,
) -> dict[str, object]:
    return {
        "data": file_data,
        "file_name": file_name,
        "language": language.value,
        "report_version": report_version,
        "options": MeetingNotesOptions.model_validate(parse_options(options).model_dump()),
        "cards": [MeetingCardVersion.model_validate(c.model_dump()) for c in parse_cards(cards)],
        "issue_number": issue_number,
        "draft": draft,
    }


@router.get("/{meeting_id}/issue", response_model=MeetingIssueResponse)
async def read_meeting_issue(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: distribution.GetMeetingIssue = Depends(deps.get_meeting_issue_use_case),
) -> MeetingIssueResponse:
    """The issue the PDF of a send carries (`send`) and the one a print or
    download carries now (`print`), which the browser prints on the PDF and
    sends back with it."""
    return _as(MeetingIssueResponse, await use_case.execute(actor, meeting_id))


@router.post(
    "/{meeting_id}/distribution/download",
    response_model=MeetingDistributionEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(max_upload_size(MAX_PDF_BYTES))],
)
async def download_meeting_notes(
    meeting_id: int,
    file: UploadFile,
    language: Language = Form(...),
    report_version: str = Form(..., min_length=1, max_length=64),
    options: str | None = _OPTIONS,
    cards: str = _CARDS,
    issue_number: int = _ISSUE,
    draft: bool = _DRAFT,
    actor: User = Depends(get_current_active_user),
    use_case: distribution.DownloadMeetingNotes = Depends(deps.get_download_meeting_notes_use_case),
) -> MeetingDistributionEntryResponse:
    """Journals the PDF the browser is about to save, with a snapshot of
    what it contains. The browser saves the file once this answered."""
    cmd = DownloadMeetingNotesCommand.model_validate(
        _build(
            await file.read(),
            file.filename,
            language,
            report_version,
            options,
            cards,
            issue_number,
            draft,
        )
    )
    return _as(MeetingDistributionEntryResponse, await use_case.execute(actor, meeting_id, cmd))


@router.post(
    "/{meeting_id}/distribution/print",
    response_model=MeetingPrintResponse,
    dependencies=[Depends(max_upload_size(MAX_PDF_BYTES))],
)
async def print_meeting_notes(
    meeting_id: int,
    file: UploadFile,
    printer_id: int = Form(...),
    copies: int = Form(default=1, ge=1, le=MAX_COPIES),
    two_sided: bool = Form(default=False),
    language: Language = Form(...),
    report_version: str = Form(..., min_length=1, max_length=64),
    options: str | None = _OPTIONS,
    cards: str = _CARDS,
    issue_number: int = _ISSUE,
    draft: bool = _DRAFT,
    actor: User = Depends(get_current_active_user),
    use_case: distribution.PrintMeetingNotes = Depends(deps.get_print_meeting_notes_use_case),
) -> MeetingPrintResponse:
    """Sends the PDF to the printer. A print that reached it answers its
    distribution entry; a printer that failed answers the failed job and
    journals nothing."""
    cmd = PrintMeetingNotesCommand.model_validate(
        {
            **_build(
                await file.read(),
                file.filename,
                language,
                report_version,
                options,
                cards,
                issue_number,
                draft,
            ),
            "printer_id": printer_id,
            "copies": copies,
            "two_sided": two_sided,
        }
    )
    return _as(MeetingPrintResponse, await use_case.execute(actor, meeting_id, cmd))


@router.post(
    "/{meeting_id}/distribution/send",
    response_model=MeetingDistributionEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(max_upload_size(MAX_PDF_BYTES))],
)
async def send_meeting_notes(
    meeting_id: int,
    file: UploadFile,
    to: str = Form(..., max_length=4000, description="Addresses separated by commas."),
    cc: str | None = Form(default=None, max_length=4000),
    subject: str = Form(..., min_length=1, max_length=500),
    html_body: str = Form(..., max_length=200_000),
    language: Language = Form(...),
    report_version: str = Form(..., min_length=1, max_length=64),
    options: str | None = _OPTIONS,
    cards: str = _CARDS,
    issue_number: int = _ISSUE,
    attach_file_ids: list[int] = Form(
        default=[], description="The meeting's documents to attach after the PDF, in order."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: distribution.SendMeetingNotes = Depends(deps.get_send_meeting_notes_use_case),
) -> MeetingDistributionEntryResponse:
    """Mails the PDF, and the documents asked for, to the recipients. The PDF
    carries the next issue (`send` of the issue route). Attachments over the
    admin size limit answer 413 naming the files that do not fit, and a mail
    server that refuses the mail answers its error; neither journals
    anything."""
    try:
        recipients = validated_recipients(to)
        copy = validated_recipients(cc, required=False) if cc else None
    except ValueError as exc:
        raise unprocessable("recipients", exc) from exc
    cmd = SendMeetingNotesCommand.model_validate(
        {
            **_build(
                await file.read(),
                file.filename,
                language,
                report_version,
                options,
                cards,
                issue_number,
                False,
            ),
            "to": recipients,
            "cc": copy or None,
            "subject": subject,
            "html_body": html_body,
            "attach_file_ids": attach_file_ids,
        }
    )
    return _as(MeetingDistributionEntryResponse, await use_case.execute(actor, meeting_id, cmd))


@router.get("/{meeting_id}/distribution", response_model=list[MeetingDistributionEntryResponse])
async def read_meeting_distribution(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: distribution.GetMeetingDistribution = Depends(deps.get_meeting_distribution_use_case),
) -> list[MeetingDistributionEntryResponse]:
    """Every print, download and send of the notes, newest first."""
    return [
        _as(MeetingDistributionEntryResponse, entry)
        for entry in await use_case.execute(actor, meeting_id)
    ]


@router.get(
    "/{meeting_id}/distribution/snapshots/{snapshot_id}", response_model=MeetingSnapshotResponse
)
async def read_meeting_snapshot(
    meeting_id: int,
    snapshot_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: distribution.GetMeetingSnapshot = Depends(deps.get_meeting_snapshot_use_case),
) -> MeetingSnapshotResponse:
    """What one print, download or send contained, for View as Sent and
    Changes Since."""
    return _as(MeetingSnapshotResponse, await use_case.execute(actor, meeting_id, snapshot_id))


@router.get(
    "/{meeting_id}/recipient-suggestions",
    response_model=list[MeetingRecipientSuggestionResponse],
)
async def read_meeting_recipient_suggestions(
    meeting_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: distribution.GetMeetingRecipientSuggestions = Depends(
        deps.get_meeting_recipient_suggestions_use_case
    ),
) -> list[MeetingRecipientSuggestionResponse]:
    """The addresses the send dialog offers, one per address with all its
    sources, the pre-selected first."""
    return [
        _as(MeetingRecipientSuggestionResponse, row)
        for row in await use_case.execute(actor, meeting_id)
    ]
