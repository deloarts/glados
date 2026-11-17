"""
Binds the checklist types to the shared controlled document use cases in
use_cases/_controlled_documents/. A new revision of a checklist whose type
has no release step supersedes the current one at once; for a type with one
the current revision stays valid until the new one is released.
"""

from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.mappers.checklist_mapper import ChecklistMapper
from src.modules.quality.application.use_cases._controlled_documents.kind import (
    ControlledDocumentKind,
)
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.services.checklist_rules import ACCESS
from src.modules.quality.domain.services.checklist_rules import ChecklistRules

KIND: ControlledDocumentKind[Checklist, ChecklistResult, ChecklistSummaryResult] = (
    ControlledDocumentKind(
        access=ACCESS,
        rules=ChecklistRules,
        live_resource=LiveResource.CHECKLISTS,
        to_result=ChecklistMapper.to_result,
        to_summary_result=ChecklistMapper.to_summary_result,
        title=lambda checklist: checklist.title,
        takes_over_now=lambda checklist: not checklist.release_required,
    )
)
