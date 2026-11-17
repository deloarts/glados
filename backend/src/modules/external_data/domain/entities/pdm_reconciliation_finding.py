"""
One row of a PDM reconciliation report (ReconcilePdmVault): an inconsistency
between the vault, pdm_file_snapshot and the catalogues, or in deep mode
between Glados and the vault's Glados.* write-back variables. Findings belong
to their run and are deleted with it; the admin dialog reads the latest
reconciliation run only.

`count` is 1 for a finding about one file or item. It is greater only for
the grouped categories (`stuck_file`, `document_unmatched`) and for
multi-file `duplicate_part_number` groups, where the item and file fields
are None. application.services.pdm_reconciliation fills each category.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PdmReconciliationFinding(Entity):
    run_id: int
    category: PdmReconciliationCategory
    severity: PdmReconciliationSeverity
    kind: str | None  # "made" | "bought" | "document" | None
    item_id: int | None
    file_id: int | None
    part_number: str | None
    revision: str | None
    message: str
    count: int
    created_at: datetime
