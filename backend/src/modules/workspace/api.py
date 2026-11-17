"""
The public API of Workspace: the project and product work ports, which Planning &
fulfillment implements: the live work and summary of a project, the summary
of a product, and what a project update does to its work; and the product
documents and meeting notes journal ports, which Quality & documents
implements.

Other modules reach this module through this file and its named interfaces:
the domain entities, events, value objects, errors and policies
(`domain/policies/`), the DTOs (`application/dto/`), the query facades
(`application/facade/`), the ports outside `ports/outbound/repositories/`
(the query ports among them) and the settings store. Everything else is internal, which the
module's protected contract in backend/.importlinter enforces.
"""

from src.modules.workspace.ports.outbound.meeting_notes_journal_port import IMeetingNotesJournal
from src.modules.workspace.ports.outbound.product_documents_port import IProductDocuments
from src.modules.workspace.ports.outbound.product_documents_port import ProductDocumentCounts
from src.modules.workspace.ports.outbound.product_documents_port import SequencedDevices
from src.modules.workspace.ports.outbound.project_work_port import IProductWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWorkPropagation
from src.modules.workspace.ports.outbound.project_work_port import ProjectCostBySupplierRow
from src.modules.workspace.ports.outbound.project_work_port import ProjectSummaryRow
from src.modules.workspace.ports.outbound.project_work_port import ProjectWorkChange

__all__ = [
    "IMeetingNotesJournal",
    "IProductDocuments",
    "IProductWork",
    "IProjectWork",
    "IProjectWorkPropagation",
    "ProductDocumentCounts",
    "ProjectCostBySupplierRow",
    "ProjectSummaryRow",
    "ProjectWorkChange",
    "SequencedDevices",
]
