"""Update production order numbering and part-number settings with validation
against external PDM patterns."""

from src.modules.catalogue.application.dto.admin_settings_dto.orders import AdminOrderSettingsResult
from src.modules.catalogue.application.dto.admin_settings_dto.orders import (
    UpdateOrderSettingsCommand,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.orders import (
    OrderSettingsMapper,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.services.item_delivery_tolerance_rules import (
    assert_valid_tolerance,
)
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.numbering_format import (
    assert_pattern_does_not_shadow_internal_formats,
)
from src.modules.platform.domain.services.numbering_format import validate_external_pattern
from src.modules.platform.domain.services.numbering_format import validate_numbering_format
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import today_in


class UpdateOrderSettings:
    def __init__(self, repo: ICatalogueSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateOrderSettingsCommand
    ) -> AdminOrderSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_orders()
        today = today_in(await tenant_zone(self._repo))
        order_number_format = (
            cmd.order_number_format
            if cmd.order_number_format is not None
            else current.order_number_format
        )
        part_number_format = (
            cmd.part_number_format
            if cmd.part_number_format is not None
            else current.part_number_format
        )
        quote_request_number_format = (
            cmd.quote_request_number_format
            if cmd.quote_request_number_format is not None
            else current.quote_request_number_format
        )
        validate_numbering_format(order_number_format)
        validate_numbering_format(part_number_format)
        validate_numbering_format(quote_request_number_format)

        pdm_part_number_pattern = (
            cmd.pdm_part_number_pattern
            if cmd.pdm_part_number_pattern is not None
            else current.pdm_part_number_pattern
        )
        validate_external_pattern(pdm_part_number_pattern)
        # Both of this domain's own numbering formats produce part
        # numbers (order_number_format numbers orders, not items, but
        # shares the same numeric space admins configure here), so both
        # are checked against the external pattern.
        assert_pattern_does_not_shadow_internal_formats(
            pdm_part_number_pattern,
            [part_number_format, order_number_format],
            today=today,
        )

        over_tolerance = (
            cmd.over_delivery_tolerance_percent
            if cmd.over_delivery_tolerance_percent is not None
            else current.over_delivery_tolerance_percent
        )
        under_tolerance = (
            cmd.under_delivery_tolerance_percent
            if cmd.under_delivery_tolerance_percent is not None
            else current.under_delivery_tolerance_percent
        )
        assert_valid_tolerance(over_tolerance, what="The over-delivery tolerance")
        assert_valid_tolerance(under_tolerance, what="The under-delivery tolerance")

        settings = AdminOrderSettings(
            id=1,
            order_number_format=order_number_format,
            part_number_format=part_number_format,
            part_number_auto=(
                cmd.part_number_auto
                if cmd.part_number_auto is not None
                else current.part_number_auto
            ),
            part_number_editable=(
                cmd.part_number_editable
                if cmd.part_number_editable is not None
                else current.part_number_editable
            ),
            web_creation_allowed=(
                cmd.web_creation_allowed
                if cmd.web_creation_allowed is not None
                else current.web_creation_allowed
            ),
            pdm_part_number_pattern=pdm_part_number_pattern,
            over_delivery_tolerance_percent=over_tolerance,
            under_delivery_tolerance_percent=under_tolerance,
            quote_request_number_format=quote_request_number_format,
        )
        saved = await self._repo.save_orders(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="orders",
                summary=f"Order settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated order settings.")
        return OrderSettingsMapper.orders_to_result(saved, today=today)
