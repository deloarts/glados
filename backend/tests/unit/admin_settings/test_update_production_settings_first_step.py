"""
UpdateProductionSettings keeps external_first_step_needs_no_material: on by
default, stored when it is sent, and left as it is when it is not.
"""

from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    UpdateProductionSettingsCommand,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_production_settings import (
    UpdateProductionSettings,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.admin_settings.fakes import FakeInspectionMethodRepository
from tests.unit.fakes import FakeUnitOfWork


class _NoLots:
    async def reset_source_approval_for_setting_change(self, enabled: bool) -> int:
        return 0


def _use_case(repo: FakeAdminSettingsRepository) -> UpdateProductionSettings:
    return UpdateProductionSettings(
        repo,
        FakeInspectionMethodRepository(),
        _NoLots(),  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
    )


ACTOR = make_user(permissions=[Permission.WRITE_SETTINGS])


async def test_on_by_default() -> None:
    assert FakeAdminSettingsRepository().production.external_first_step_needs_no_material is True


async def test_turning_it_off_is_stored() -> None:
    repo = FakeAdminSettingsRepository()

    result = await _use_case(repo).execute(
        ACTOR, UpdateProductionSettingsCommand(external_first_step_needs_no_material=False)
    )

    assert result.external_first_step_needs_no_material is False
    assert (await repo.get_production()).external_first_step_needs_no_material is False


async def test_an_update_without_it_keeps_it() -> None:
    repo = FakeAdminSettingsRepository()
    repo.production.external_first_step_needs_no_material = False

    result = await _use_case(repo).execute(
        ACTOR, UpdateProductionSettingsCommand(response_time_days=3)
    )

    assert result.external_first_step_needs_no_material is False
