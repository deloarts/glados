"""
Print-template settings surface (GET/PATCH only, since every classifier has
exactly one row, created at startup and never deleted), field sources for the frontend's field-map editor,
and preview (text + PNG).
"""

from fastapi import Depends
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.printing import (
    get_download_print_document_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.printing import (
    get_preview_print_template_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.printing import get_print_template_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_print_templates_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import (
    get_render_print_template_image_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.printing import get_reset_print_template_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import (
    get_update_print_template_use_case,
)
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import (
    FieldSourceResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import PreviewResponse
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import (
    PrintTemplateResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import (
    PrintTemplateUpdateRequest,
)
from src.modules.quality.application.dto.print_template_dto import FieldSourceResult
from src.modules.quality.application.dto.print_template_dto import PreviewPrintTemplateResult
from src.modules.quality.application.dto.print_template_dto import PrintTemplateResult
from src.modules.quality.application.dto.print_template_dto import UpdatePrintTemplateCommand
from src.modules.quality.application.services.print_field_sources import field_sources_for
from src.modules.quality.application.use_cases.print_document.download_print_document import (
    DownloadPrintDocument,
)
from src.modules.quality.application.use_cases.print_template.get_print_templates import (
    GetPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.get_print_templates import (
    GetPrintTemplates,
)
from src.modules.quality.application.use_cases.print_template.preview_print_template import (
    PreviewPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.render_print_template_image import (
    RenderPrintTemplateImage,
)
from src.modules.quality.application.use_cases.print_template.reset_print_template import (
    ResetPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.update_print_template import (
    UpdatePrintTemplate,
)
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger

router = APIRouter()


# Deliberately unpaginated: bounded per-classifier collection.
@router.get("/", response_model=list[PrintTemplateResponse])
async def read_print_templates(
    _: User = Depends(get_current_active_user),
    use_case: GetPrintTemplates = Depends(get_print_templates_use_case),
) -> list[PrintTemplateResult]:
    return await use_case.execute()


@router.get("/{classifier}", response_model=PrintTemplateResponse)
async def read_print_template(
    classifier: str,
    _: User = Depends(get_current_active_user),
    use_case: GetPrintTemplate = Depends(get_print_template_use_case),
) -> PrintTemplateResult:
    return await use_case.execute(classifier)


@router.patch("/{classifier}", response_model=PrintTemplateResponse)
async def update_print_template(
    classifier: str,
    body: PrintTemplateUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdatePrintTemplate = Depends(get_update_print_template_use_case),
) -> PrintTemplateResult:
    cmd = UpdatePrintTemplateCommand(**body.model_dump(exclude_unset=True))
    return await use_case.execute(actor=actor, classifier=classifier, cmd=cmd)


@router.post("/{classifier}/reset", response_model=PrintTemplateResponse)
async def reset_print_template(
    classifier: str,
    actor: User = Depends(get_current_active_user),
    use_case: ResetPrintTemplate = Depends(get_reset_print_template_use_case),
) -> PrintTemplateResult:
    return await use_case.execute(actor=actor, classifier=classifier)


@router.get("/{classifier}/field-sources", response_model=list[FieldSourceResponse])
async def read_field_sources(
    classifier: PrintClassifier,
    trigger: PrintTrigger | None = None,
    _: User = Depends(get_current_active_user),
) -> list[FieldSourceResult]:
    """Pure lookup against the classifier/trigger registry: no repo is
    needed, so no use case, just the registry function directly. FastAPI
    validates classifier/trigger against the enums (422 on an unknown
    value) before this body runs."""
    sources = field_sources_for(classifier, trigger)
    return [FieldSourceResult(name=s.name, kind=s.kind, description=s.description) for s in sources]


@router.post("/{classifier}/preview", response_model=PreviewResponse)
async def preview_print_template(
    classifier: str,
    root_type: str,
    root_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: PreviewPrintTemplate = Depends(get_preview_print_template_use_case),
) -> PreviewPrintTemplateResult:
    return await use_case.execute(actor, classifier, root_type, root_id)


@router.post("/{classifier}/preview.png")
async def preview_print_template_image(
    classifier: str,
    root_type: str,
    root_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RenderPrintTemplateImage = Depends(get_render_print_template_image_use_case),
) -> Response:
    png, warnings = await use_case.execute(actor, classifier, root_type, root_id)
    headers = {"X-Preview-Warnings": ", ".join(warnings)} if warnings else {}
    return Response(content=png, media_type="image/png", headers=headers)


@router.post("/{classifier}/download")
async def download_print_template(
    classifier: str,
    root_type: str,
    root_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DownloadPrintDocument = Depends(get_download_print_document_use_case),
) -> Response:
    """No printer involved at all: renders exactly what a print would send
    and hands the bytes straight back as a file. This is the generic download
    path every classifier gets, dockets included, that PrintDocument's
    printer-based path does not require."""
    rendered = await use_case.execute(actor, classifier, root_type, root_id)
    extension = "pdf" if rendered.content_type == "application/pdf" else "zpl"
    headers = {"Content-Disposition": f'attachment; filename="{classifier}.{extension}"'}
    if rendered.warnings:
        headers["X-Preview-Warnings"] = ", ".join(rendered.warnings)
    return Response(content=rendered.payload, media_type=rendered.content_type, headers=headers)
