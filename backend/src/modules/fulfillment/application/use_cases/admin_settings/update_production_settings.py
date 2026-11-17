"""
Updates the production settings and audits the change in one unit of work.
Flipping require_source_item_approval backfills the source approval state
of existing lots, and that backfill must land together with the settings
row or not at all: a row that says "on" next to a half-applied backfill
would leave some lots demandable that should be pending. The backfill, the
settings save and the audit entry therefore share the request's session
and commit once at the end.
"""

from src.modules.catalogue.domain.errors import InspectionMethodConfigurationError
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    AdminProductionSettingsResult,
)
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    UpdateProductionSettingsCommand,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.production import (
    ProductionSettingsMapper,
)
from src.modules.fulfillment.application.mappers.machine_calendar_mapper import (
    weekly_hours_from_dto,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.services.scheduling import validate_weekly_hours
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.numbering_format import validate_numbering_format
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import today_in


class UpdateProductionSettings:
    def __init__(
        self,
        repo: IFulfillmentSettingsRepository,
        inspection_method_repo: IInspectionMethodQueries,
        lot_repo: IProductionLotRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._repo = repo
        self._inspection_methods = inspection_method_repo
        self._lots = lot_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, cmd: UpdateProductionSettingsCommand
    ) -> AdminProductionSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_production()
        production_order_number_format = (
            cmd.production_order_number_format
            if cmd.production_order_number_format is not None
            else current.production_order_number_format
        )
        default_weekly_hours = (
            weekly_hours_from_dto(cmd.default_weekly_hours)
            if cmd.default_weekly_hours is not None
            else current.default_weekly_hours
        )
        default_external_lead_days = (
            cmd.default_external_lead_days
            if cmd.default_external_lead_days is not None
            else current.default_external_lead_days
        )
        response_time_days = (
            cmd.response_time_days
            if cmd.response_time_days is not None
            else current.response_time_days
        )
        require_qa = cmd.require_qa if cmd.require_qa is not None else current.require_qa
        frozen_window_hours = (
            cmd.frozen_window_hours
            if cmd.frozen_window_hours is not None
            else current.frozen_window_hours
        )
        default_inspection_method_id = (
            cmd.default_inspection_method_id
            if cmd.default_inspection_method_id is not None
            else current.default_inspection_method_id
        )
        require_source_item_approval = (
            cmd.require_source_item_approval
            if cmd.require_source_item_approval is not None
            else current.require_source_item_approval
        )
        assign_approved_material_to_item = (
            cmd.assign_approved_material_to_item
            if cmd.assign_approved_material_to_item is not None
            else current.assign_approved_material_to_item
        )
        overwrite_item_material_on_approval = (
            cmd.overwrite_item_material_on_approval
            if cmd.overwrite_item_material_on_approval is not None
            else current.overwrite_item_material_on_approval
        )
        validate_numbering_format(production_order_number_format)
        validate_weekly_hours(default_weekly_hours)

        if require_qa:
            method = (
                await self._inspection_methods.get_by_id(default_inspection_method_id)
                if default_inspection_method_id is not None
                else None
            )
            if method is None:
                raise InspectionMethodConfigurationError(
                    "require_qa needs a default_inspection_method_id set to an existing, "
                    "non-archived inspection method."
                )
            if method.archived:
                raise InspectionMethodConfigurationError(
                    f"Inspection method {method.name!r} is archived and cannot be the "
                    "require_qa default."
                )

        settings = AdminProductionSettings(
            id=1,
            production_order_number_format=production_order_number_format,
            default_weekly_hours=default_weekly_hours,
            default_external_lead_days=default_external_lead_days,
            response_time_days=response_time_days,
            require_qa=require_qa,
            default_inspection_method_id=default_inspection_method_id,
            require_source_item_approval=require_source_item_approval,
            assign_approved_material_to_item=assign_approved_material_to_item,
            overwrite_item_material_on_approval=overwrite_item_material_on_approval,
            frozen_window_hours=frozen_window_hours,
        )

        # The backfill and the settings save commit together below (see this
        # module's docstring).
        setting_flipped = require_source_item_approval != current.require_source_item_approval
        if setting_flipped:
            updated = await self._lots.reset_source_approval_for_setting_change(
                enabled=require_source_item_approval
            )
            log.info(
                f"require_source_item_approval flipped to {require_source_item_approval}; "
                f"backfilled {updated} lot(s)."
            )

        saved = await self._repo.save_production(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="production",
                summary=f"Production settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute,
            after="changing the production settings; the change itself is committed.",
        )

        log.info("Updated production settings.")
        return ProductionSettingsMapper.production_to_result(
            saved, today=today_in(await tenant_zone(self._repo))
        )
