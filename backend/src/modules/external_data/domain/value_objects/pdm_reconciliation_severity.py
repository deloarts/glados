"""
How urgently a PdmReconciliationFinding deserves an admin's attention:
`info` for something worth knowing but not wrong on its own (an unreadable
datacard during a deep write-back check, a WEB item PDM could now claim),
`warning` for a data inconsistency that will resolve itself on the next
successful poll or ingest (a stuck file, a revision lag, a kind mismatch),
`error` for something reconciliation cannot fix by itself and that likely
needs a manual look (a duplicate part number, an orphaned registry entry).
"""

from enum import Enum
from enum import unique


@unique
class PdmReconciliationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
