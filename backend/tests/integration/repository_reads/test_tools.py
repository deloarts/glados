"""
Read scenarios for what the engineering tools store: saved calculations,
checklists and flow sequences, and the journal of the PDF reports exported
from them. See the package docstring for how the scenarios work.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.quality.adapters.outbound.persistence.repositories.calculation_repository import (
    SqlAlchemyCalculationRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.checklist_repository import (
    SqlAlchemyChecklistRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.report_journal_repository import (
    SqlAlchemyReportJournalRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.sequence_repository import (
    SqlAlchemySequenceRepository,
)
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.entities.report_journal_entry import ReportJournalEntry
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    CalculationFilterDto,
)
from src.modules.quality.ports.outbound.repositories.checklist_repository import ChecklistFilterDto
from src.modules.quality.ports.outbound.repositories.sequence_repository import SequenceFilterDto
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()


@SCENARIOS.register(SqlAlchemyCalculationRepository)
async def _calculations(g: Graph, r: Any) -> None:
    """A released project calculation and a product calculation, so the
    project, product, creator and released_by relationships all load."""
    project_calc = await g.calculation()
    await SqlAlchemyCalculationRepository(g.db).save(
        make(
            Calculation,
            document_number="CAL-26-0002",
            tool="fit_calculator",
            title="Shaft",
            product_id=(await g.product()).id,
            creator_id=g.uid,
        )
    )
    await g.db.commit()

    await r.get_by_id(project_calc.id)
    await r.get_for_update(project_calc.id)
    await r.get_by_public_id(project_calc.public_id)
    await r.get_multi(CalculationFilterDto())
    await r.get_lineage(project_calc.lineage)
    await r.next_document_number("CAL-{yy}-{seq:04d}")


@SCENARIOS.register(SqlAlchemyChecklistRepository)
async def _checklists(g: Graph, r: Any) -> None:
    """A released project checklist and a product checklist, so the
    project, product, creator and released_by relationships all load."""
    project_checklist = await g.checklist()
    await SqlAlchemyChecklistRepository(g.db).save(
        make(
            Checklist,
            document_number="CHK-26-0002",
            type="pneumatics",
            title="Gripper pneumatics",
            verdict=ChecklistVerdict.OPEN,
            product_id=(await g.product()).id,
            creator_id=g.uid,
        )
    )
    await g.db.commit()

    await r.get_by_id(project_checklist.id)
    await r.get_for_update(project_checklist.id)
    await r.get_by_public_id(project_checklist.public_id)
    await r.get_multi(ChecklistFilterDto())
    await r.get_lineage(project_checklist.lineage)
    await r.next_document_number("CHK-{yy}-{seq:04d}")


@SCENARIOS.register(SqlAlchemyReportJournalRepository)
async def _report_journal(g: Graph, r: Any) -> None:
    """A download of the calculation's report, so the actor relationship
    loads."""
    calculation = await g.calculation()
    await SqlAlchemyReportJournalRepository(g.db).save(
        make(
            ReportJournalEntry,
            created=NOW,
            actor_id=g.uid,
            action=ReportJournalAction.DOWNLOAD,
            document=UploadedPrintDocument.CALCULATION_REPORT,
            root_type=PrintRootType.CALCULATION,
            root_id=calculation.id,
            lineage=calculation.lineage,
            revision=calculation.revision,
            language="enGB",
            options={"show_inputs": True},
            report_version="1",
            engine_version=1,
            byte_size=1024,
            sha256="0" * 64,
        )
    )
    await g.db.commit()

    await r.list_for_lineage(PrintRootType.CALCULATION.value, calculation.lineage)
    await r.count_for_lineages(PrintRootType.CALCULATION.value, [calculation.lineage])


@SCENARIOS.register(SqlAlchemySequenceRepository)
async def _sequences(g: Graph, r: Any) -> None:
    """A released sequence of the product, so the product, creator and
    released_by relationships all load."""
    sequence = await SqlAlchemySequenceRepository(g.db).save(
        make(
            Sequence,
            document_number="SEQ-26-0001",
            product_id=(await g.product()).id,
            name="Automatic",
            creator_id=g.uid,
            released_at=NOW,
            released_by_id=g.other_user.id,
        )
    )
    await g.db.commit()

    await r.get_by_id(sequence.id)
    await r.get_for_update(sequence.id)
    await r.get_by_public_id(sequence.public_id)
    await r.get_multi(SequenceFilterDto())
    await r.get_lineage(sequence.lineage)
    await r.next_document_number("SEQ-{yy}-{seq:04d}")


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
