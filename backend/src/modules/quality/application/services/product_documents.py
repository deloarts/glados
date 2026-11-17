"""
Workspace's view of a product's documents (IProductDocuments): the released
calculations and checklists a renumbering affects with their exports, and
the devices the product's sequences reference.
"""

from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.quality.domain.services.sequence_rules import references_of
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    CalculationFilterDto,
)
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)
from src.modules.quality.ports.outbound.repositories.checklist_repository import ChecklistFilterDto
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository
from src.modules.quality.ports.outbound.repositories.sequence_repository import SequenceFilterDto
from src.modules.workspace.api import ProductDocumentCounts
from src.modules.workspace.api import SequencedDevices

# Lineages read for the export count; a product with more documents than
# this is counted on the first ones, which is enough for a warning.
LINEAGE_LIMIT = 500


class ProductDocuments:
    """IProductDocuments over the calculation, checklist, report journal and
    sequence repositories."""

    def __init__(
        self,
        calculation_repo: ICalculationRepository,
        checklist_repo: IChecklistRepository,
        journal_repo: IReportJournalRepository,
        sequence_repo: ISequenceRepository,
    ) -> None:
        self._calculations = calculation_repo
        self._checklists = checklist_repo
        self._journal = journal_repo
        self._sequences = sequence_repo

    async def renumber_counts(self, product_id: int) -> ProductDocumentCounts:
        released_calculations, _ = await self._calculations.get_multi(
            CalculationFilterDto(
                related_product_id=product_id, released=True, latest_only=False, limit=1
            )
        )
        released_checklists, _ = await self._checklists.get_multi(
            ChecklistFilterDto(
                related_product_id=product_id, released=True, latest_only=False, limit=1
            )
        )
        _, calculations = await self._calculations.get_multi(
            CalculationFilterDto(related_product_id=product_id, limit=LINEAGE_LIMIT)
        )
        _, checklists = await self._checklists.get_multi(
            ChecklistFilterDto(related_product_id=product_id, limit=LINEAGE_LIMIT)
        )
        exports = await self._journal.count_for_lineages(
            PrintRootType.CALCULATION.value, [c.lineage for c in calculations]
        ) + await self._journal.count_for_lineages(
            PrintRootType.CHECKLIST.value, [c.lineage for c in checklists]
        )
        return ProductDocumentCounts(
            released=released_calculations + released_checklists, exports=exports
        )

    async def sequenced_devices(self, product_id: int) -> SequencedDevices:
        sequences = await fetch_all(
            lambda skip, limit: self._sequences.get_multi(
                SequenceFilterDto(product_id=product_id, latest_only=False, skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        released: set[int] = set()
        drafts: set[int] = set()
        for sequence in sequences:
            ids = references_of(sequence.steps).device_ids
            if sequence.is_released and not sequence.superseded_at and not sequence.is_invalid:
                released |= ids
            elif sequence.is_latest and not sequence.is_released:
                drafts |= ids
        return SequencedDevices(released=frozenset(released), drafts=frozenset(drafts))
