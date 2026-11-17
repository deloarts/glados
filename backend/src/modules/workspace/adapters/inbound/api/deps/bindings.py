"""
The dependencies of Workspace's routes whose implementations live in the
modules above it, which the composition root binds at startup
(`src/bootstrap/bindings.py`).
"""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.binding import Binding
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import IMeetingNotesJournal
from src.modules.workspace.ports.outbound.product_documents_port import IProductDocuments
from src.modules.workspace.ports.outbound.project_work_port import IProductWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWorkPropagation

project_work: Binding[Callable[[AsyncSession], IProjectWork]] = Binding("The work of a project")
product_work: Binding[Callable[[AsyncSession], IProductWork]] = Binding("The work of a product")
project_work_propagation: Binding[Callable[[AsyncSession], IProjectWorkPropagation]] = Binding(
    "The propagation of a project update to its work"
)
product_documents: Binding[Callable[[AsyncSession], IProductDocuments]] = Binding(
    "The documents of a product"
)
meeting_notes_journal: Binding[Callable[[AsyncSession], IMeetingNotesJournal]] = Binding(
    "The export journal of meeting notes"
)


def get_project_work(db: AsyncSession = Depends(get_db, scope="function")) -> IProjectWork:
    return project_work.get()(db)


def get_product_work(db: AsyncSession = Depends(get_db, scope="function")) -> IProductWork:
    return product_work.get()(db)


def get_project_work_propagation(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IProjectWorkPropagation:
    return project_work_propagation.get()(db)


def get_product_documents(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IProductDocuments:
    return product_documents.get()(db)


def get_meeting_notes_journal(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IMeetingNotesJournal:
    return meeting_notes_journal.get()(db)
