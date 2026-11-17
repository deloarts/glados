"""Repository factories on the request's session."""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_order_interruption_repo,
)
from src.modules.fulfillment.ports.outbound.fulfillment_queries import (
    IProductionOrderInterruptionQueries,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory
from src.modules.quality.adapters.outbound.persistence.repositories.calculation_repository import (
    SqlAlchemyCalculationRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.checklist_repository import (
    SqlAlchemyChecklistRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_job_repository import (
    SqlAlchemyPrintJobRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.printer_repository import (
    SqlAlchemyPrinterRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.production_kpi_repository import (
    SqlAlchemyProductionKpiRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.report_journal_repository import (
    SqlAlchemyReportJournalRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.sequence_repository import (
    SqlAlchemySequenceRepository,
)
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    IProductionKpiRepository,
)
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository

get_printer_repo: Callable[[AsyncSession], IPrinterRepository] = repo_factory(
    SqlAlchemyPrinterRepository
)
get_print_template_repo: Callable[[AsyncSession], IPrintTemplateRepository] = repo_factory(
    SqlAlchemyPrintTemplateRepository
)
get_print_job_repo: Callable[[AsyncSession], IPrintJobRepository] = repo_factory(
    SqlAlchemyPrintJobRepository
)
get_calculation_repo: Callable[[AsyncSession], ICalculationRepository] = repo_factory(
    SqlAlchemyCalculationRepository
)
get_checklist_repo: Callable[[AsyncSession], IChecklistRepository] = repo_factory(
    SqlAlchemyChecklistRepository
)
get_sequence_repo: Callable[[AsyncSession], ISequenceRepository] = repo_factory(
    SqlAlchemySequenceRepository
)
get_report_journal_repo: Callable[[AsyncSession], IReportJournalRepository] = repo_factory(
    SqlAlchemyReportJournalRepository
)


def get_production_kpi_repo(
    db: AsyncSession = Depends(get_db, scope="function"),
    interruption_repo: IProductionOrderInterruptionQueries = Depends(
        get_production_order_interruption_repo
    ),
) -> IProductionKpiRepository:
    """Also wires the interruption repository for net work minutes."""
    return SqlAlchemyProductionKpiRepository(db, interruption_repo)
