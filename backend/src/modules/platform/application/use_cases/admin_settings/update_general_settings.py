"""Update general system configuration (company info, number patterns, locale
settings) with partial update semantics."""

from src.modules.platform.application.dto.admin_settings_dto.general import (
    AdminGeneralSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.general import (
    UpdateGeneralSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.general import (
    GeneralSettingsMapper,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.number_pattern import validate_pattern
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateGeneralSettings:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, cmd: UpdateGeneralSettingsCommand
    ) -> AdminGeneralSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_general()
        product_number_pattern = (
            cmd.product_number_pattern
            if cmd.product_number_pattern is not None
            else current.product_number_pattern
        )
        project_number_pattern = (
            cmd.project_number_pattern
            if cmd.project_number_pattern is not None
            else current.project_number_pattern
        )

        # Both patterns are validated even when only one was submitted: an
        # uncompilable pattern must never reach the DB, because every
        # project/product create and update runs against it.
        validate_pattern(product_number_pattern)
        validate_pattern(project_number_pattern)

        settings = AdminGeneralSettings(
            id=1,
            company_name=(
                cmd.company_name if cmd.company_name is not None else current.company_name
            ),
            company_legal_name=(
                cmd.company_legal_name
                if cmd.company_legal_name is not None
                else current.company_legal_name
            ),
            # Never set from this command: the logo is written only by the
            # dedicated upload/delete use cases, which also manage the object
            # in storage.
            company_logo_key=current.company_logo_key,
            contact_email=(
                cmd.contact_email if cmd.contact_email is not None else current.contact_email
            ),
            imprint_url=(cmd.imprint_url if cmd.imprint_url is not None else current.imprint_url),
            privacy_url=(cmd.privacy_url if cmd.privacy_url is not None else current.privacy_url),
            support_url=(cmd.support_url if cmd.support_url is not None else current.support_url),
            product_number_pattern=product_number_pattern,
            project_number_pattern=project_number_pattern,
            allow_headless_projects=(
                cmd.allow_headless_projects
                if cmd.allow_headless_projects is not None
                else current.allow_headless_projects
            ),
            empty_value_placeholder=(
                cmd.empty_value_placeholder
                if cmd.empty_value_placeholder is not None
                else current.empty_value_placeholder
            ),
            office_launcher_enabled=(
                cmd.office_launcher_enabled
                if cmd.office_launcher_enabled is not None
                else current.office_launcher_enabled
            ),
            office_sharepoint_url=(
                cmd.office_sharepoint_url
                if cmd.office_sharepoint_url is not None
                else current.office_sharepoint_url
            ),
            currency=(cmd.currency if cmd.currency is not None else current.currency),
            default_language=(
                cmd.default_language
                if cmd.default_language is not None
                else current.default_language
            ),
            default_timezone=(
                cmd.default_timezone
                if cmd.default_timezone is not None
                else current.default_timezone
            ),
            default_date_format=(
                cmd.default_date_format
                if cmd.default_date_format is not None
                else current.default_date_format
            ),
        )
        saved = await self._repo.save_general(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="general",
                summary=f"General settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="changing the general settings; the change itself is committed."
        )

        log.info("Updated general settings.")
        return GeneralSettingsMapper.general_to_result(saved)
