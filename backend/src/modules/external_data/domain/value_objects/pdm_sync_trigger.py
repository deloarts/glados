"""
What set a PdmSyncRun in motion: `scheduled` for the poller's own 60s-tick
gate, `manual` for an admin's manual sync-now request (which works by
clearing last_poll_at, the same value a vault that has genuinely never
been polled starts with), and `initial` for that genuinely-first-ever
poll. RunPdmPollIfDue is the only place that can tell the three apart, by
checking whether a `scheduled` or `manual` run has ever been recorded
before (see its own docstring). `file_trigger` is for the vault add-in's
change-notification endpoint, `retry` for the admin "PDM files" pending
list's Retry action, and `reconciliation` for ReconcilePdmVault (the
reconciliation report, docs/reference/pdm-admin.md section 7): a quick or deep drift report, queued by
`AdminPdmSettings.reconcile_requested_deep` and run by the same tick that
checks the poll interval, never on its own schedule. The entity keeps a
plain `trigger: str` field, mirroring PdmFileSyncState's precedent; the
application layer constructs/compares with this enum, the repository
stores/reads the plain value.
"""

from enum import Enum
from enum import unique


@unique
class PdmSyncTrigger(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    INITIAL = "initial"
    FILE_TRIGGER = "file_trigger"
    RETRY = "retry"
    RECONCILIATION = "reconciliation"
