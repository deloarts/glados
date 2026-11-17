"""Updates the stock service settings (see
docs/reference/stock-service.md section 1).

Shape checks (URL form) are request validators; this use case enforces the
rule that needs the merged result: enabling only with a service URL and an
API key. The audit entry names an old and a new URL, and says when the API
key changed, never what it is.
"""

from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    AdminStockSettingsResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    UpdateStockSettingsCommand,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.stock import (
    StockSettingsMapper,
)
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateStockSettings:
    def __init__(self, repo: IExternalDataSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateStockSettingsCommand
    ) -> AdminStockSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_stock()
        service_url = cmd.service_url if cmd.service_url is not None else current.service_url
        api_key = (
            current.api_key
            if cmd.api_key is None
            else (cmd.api_key.get_secret_value().strip() or None)
        )
        settings = AdminStockSettings(
            id=1,
            public_id=current.public_id,
            enabled=cmd.enabled if cmd.enabled is not None else current.enabled,
            service_url=service_url,
            api_key=api_key,
        )
        settings.assert_valid()

        saved = await self._repo.save_stock(settings)
        changes: list[str] = []
        if saved.service_url != current.service_url:
            changes.append(
                f"service changed from {current.service_url or '(none)'} to "
                f"{saved.service_url or '(none)'}"
            )
        if api_key != current.api_key:
            changes.append("API key changed")
        summary = f"Stock service settings updated by {actor.username}"
        summary += f", {'; '.join(changes)}." if changes else "."
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(actor, settings_domain="stock", summary=summary)
        )
        await self._uow.commit()

        log.info("Updated the stock service settings.")
        return StockSettingsMapper.stock_to_result(saved)
