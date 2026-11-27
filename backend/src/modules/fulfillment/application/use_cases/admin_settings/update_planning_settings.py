"""
Updates the planning settings and audits the change in one unit of work. A
field left out keeps its value. booking_quality_since is not editable: it
marks when the planning features started to judge bookings, and moving it
would hide or bring back what the booking quality view reported.
"""

from dataclasses import replace

from src.modules.fulfillment.application.dto.admin_settings_dto.planning import (
    AdminPlanningSettingsResult,
)
from src.modules.fulfillment.application.dto.admin_settings_dto.planning import (
    UpdatePlanningSettingsCommand,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.planning import (
    PlanningSettingsMapper,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdatePlanningSettings:
    def __init__(self, repo: IFulfillmentSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdatePlanningSettingsCommand
    ) -> AdminPlanningSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_planning()
        settings = replace(
            current,
            commit_horizon_working_days=(
                cmd.commit_horizon_working_days
                if cmd.commit_horizon_working_days is not None
                else current.commit_horizon_working_days
            ),
            plan_retention_days=(
                cmd.plan_retention_days
                if cmd.plan_retention_days is not None
                else current.plan_retention_days
            ),
        )
        saved = await self._repo.save_planning(settings)
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="planning",
                summary=f"Planning settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated planning settings.")
        return PlanningSettingsMapper.planning_to_result(saved)
