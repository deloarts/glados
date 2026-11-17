"""
Manual print actions. POST /print fans out to one PrintDocument.execute()
call per requested classifier, so a label and a docket can be printed in
one action once dockets are implemented. PrintDocument never raises for a
pipeline failure (see its docstring): each item's outcome, success or
failure, comes back as its own PrintJobResult, so one bad classifier
(wrong printer kind, unreachable printer) never hides the others'.

POST /print/document takes a finished PDF the browser rendered, such as a
calculation report, and sends it to the chosen printer unchanged.
"""

from uuid import UUID

from fastapi import Depends
from fastapi import Form
from fastapi import UploadFile
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.upload_limits import max_upload_size
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.printing import get_print_document_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import (
    get_print_uploaded_document_use_case,
)
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import PrintJobResponse
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import PrintRequestBody
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import (
    UploadedPrintJobResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.report_journal_schema import export_facts
from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.dto.print_template_dto import PrintUploadedDocumentCommand
from src.modules.quality.application.dto.print_template_dto import UploadedPrintJobResult
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    MAX_BYTES,
)
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    MAX_COPIES,
)
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    PrintUploadedDocument,
)
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument

router = APIRouter()


@router.post("/", response_model=list[PrintJobResponse])
async def print_document(
    body: PrintRequestBody,
    actor: User = Depends(get_current_active_user),
    use_case: PrintDocument = Depends(get_print_document_use_case),
) -> list[PrintJobResult]:
    return [
        await use_case.execute(
            actor,
            item.classifier,
            body.root_type,
            body.root_id,
            printer_id=item.printer_id,
            copies=item.copies,
        )
        for item in body.items
    ]


@router.post(
    "/document",
    response_model=UploadedPrintJobResponse,
    dependencies=[Depends(max_upload_size(MAX_BYTES))],
)
async def print_uploaded_document(
    file: UploadFile,
    document: UploadedPrintDocument = Form(...),
    root_public_id: UUID = Form(...),
    printer_id: int = Form(...),
    copies: int = Form(default=1, ge=1, le=MAX_COPIES),
    two_sided: bool = Form(default=False),
    language: str | None = Form(default=None, max_length=16),
    options: str | None = Form(
        default=None, max_length=2000, description="The report options as a JSON object"
    ),
    report_version: str | None = Form(default=None, max_length=64),
    engine_version: int | None = Form(default=None, ge=1),
    actor: User = Depends(get_current_active_user),
    use_case: PrintUploadedDocument = Depends(get_print_uploaded_document_use_case),
) -> UploadedPrintJobResult:
    return await use_case.execute(
        actor,
        PrintUploadedDocumentCommand(
            document=document.value,
            root_public_id=root_public_id,
            printer_id=printer_id,
            copies=copies,
            two_sided=two_sided,
            data=await file.read(),
            facts=export_facts(language, options, report_version, engine_version),
        ),
    )
