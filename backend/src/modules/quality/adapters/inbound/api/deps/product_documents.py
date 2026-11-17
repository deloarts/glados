"""Quality & documents' implementation of Workspace's product documents port,
which the composition root binds at startup."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.quality.adapters.inbound.api.deps.repositories import get_calculation_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_checklist_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_report_journal_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_sequence_repo
from src.modules.quality.application.services.product_documents import ProductDocuments
from src.modules.workspace.api import IProductDocuments


def build_product_documents(db: AsyncSession) -> IProductDocuments:
    """The documents of a product on one session."""
    return ProductDocuments(
        get_calculation_repo(db),
        get_checklist_repo(db),
        get_report_journal_repo(db),
        get_sequence_repo(db),
    )
