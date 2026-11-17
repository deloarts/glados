"""
Records the security-relevant terminal actions (terminal key creation,
approval, revocation, screen reassignment, deletion and clone detection) in
the admin settings audit trail under the `terminals` domain, next to a log
line. A detection by the system itself has no actor.
"""

from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.clock import now_utc

TERMINALS_AUDIT_DOMAIN = "terminals"


async def record_terminal_audit(
    settings_repo: IOperationsSettingsRepository, actor: User | None, summary: str
) -> None:
    """Appends the entry in the caller's transaction; the caller commits."""
    if actor is not None:
        entry = AdminSettingsAuditEntry.by_actor(
            actor, settings_domain=TERMINALS_AUDIT_DOMAIN, summary=summary
        )
    else:
        entry = AdminSettingsAuditEntry(
            id=0,
            changed_at=now_utc(),
            changed_by_id=None,
            changed_by_username=None,
            settings_domain=TERMINALS_AUDIT_DOMAIN,
            summary=summary,
        )
    await settings_repo.append_audit(entry)
