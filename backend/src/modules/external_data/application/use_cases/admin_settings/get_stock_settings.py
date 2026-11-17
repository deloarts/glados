"""Routes GET /admin/settings/stock through the use-case layer."""

from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    AdminStockSettingsResult,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.stock import (
    StockSettingsMapper,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetStockSettings:
    def __init__(self, repo: IExternalDataSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminStockSettingsResult:
        SettingsRules.assert_can_read(actor)
        return StockSettingsMapper.stock_to_result(await self._repo.get_stock())
