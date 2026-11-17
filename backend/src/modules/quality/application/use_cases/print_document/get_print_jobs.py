"""
Retrieves paginated print job records, gated on READ_SETTINGS permission for cross-user
audit-log access.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.mappers.print_template_mapper import PrintJobMapper
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.print_job_repository import PrintJobFilterDto


class PaginatedPrintJobs:
    def __init__(self, total: int, items: list[PrintJobResult]):
        self.total = total
        self.items = items


class GetPrintJobs:
    def __init__(self, job_repo: IPrintJobRepository) -> None:
        self._jobs = job_repo

    async def execute(self, actor: User, filters: PrintJobFilterDto) -> PaginatedPrintJobs:
        # The full cross-user print audit log, gated like every other
        # audit-shaped surface (logs.py, admin_settings/audit.py,
        # webhooks.py deliveries).
        assert_has_permission(actor, Permission.READ_SETTINGS, "read", "print jobs")

        total, items = await self._jobs.get_multi(filters)
        return PaginatedPrintJobs(total=total, items=[PrintJobMapper.to_result(i) for i in items])
